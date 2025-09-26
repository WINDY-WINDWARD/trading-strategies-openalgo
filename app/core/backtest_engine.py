# app/core/backtest_engine.py
"""
Main backtesting engine with event-driven architecture.
"""
import asyncio

import time
import uuid
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import logging
from tqdm import tqdm

from ..models.config import AppConfig
from ..strategies.base_strategy import BaseStrategy
from ..models.market_data import Candle
from ..models.orders import Order, OrderStatus, OrderType, OrderAction
from ..models.results import BacktestResult, Trade, EquityPoint
from ..core.portfolio import Portfolio
from ..core.order_simulator import OrderSimulator
from ..core.metrics import MetricsCalculator
from ..core.events import (
    EventQueue, MarketDataEvent, OrderEvent, FillEvent,
    PortfolioEvent
)


logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Features:
    - Event-driven architecture
    - Realistic order execution simulation  
    - Comprehensive performance tracking
    - Strategy integration
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtesting configuration
        """
        self.config = config
        self.run_id = config.run_id
        
        # Core components
        self.portfolio = Portfolio(config.backtest.initial_cash)
        self.order_simulator = OrderSimulator(
            slippage_bps=config.backtest.slippage_bps,
            seed=config.backtest.seed
        )
        self.metrics_calculator = MetricsCalculator()
        self.event_queue = EventQueue()
        
        # State
        self.current_time: Optional[datetime] = None
        self.current_tick: int = 0
        self.active_orders: Dict[str, Order] = {}
        self.completed_trades: List[Trade] = []
        self.order_history: List[Order] = []  # Track all orders for better trade matching
        self.is_running = False
        
        # Strategy callback
        self.strategy: Optional[BaseStrategy] = None
        self.progress_callback: Optional[Callable] = None
        
        # Progress tracking
        self.total_candles = 0
        self.processed_candles = 0
        self.total_ticks = 0
        self.processed_ticks = 0
        
        logger.info(f"Backtest engine initialized: {self.run_id}")
    
    def set_strategy(self, strategy: BaseStrategy) -> None:
        """
        Set strategy callback function.
        
        Args:
            strategy: An instance of a class that inherits from BaseStrategy.
        """
        self.strategy = strategy
        self.strategy.set_context(self) # Provide context to the strategy
        logger.info("Strategy callback registered")
    
    def run_backtest(self, market_data: List[Candle]) -> BacktestResult:
        """
        Run complete backtest.
        
        Args:
            market_data: List of historical candles
            
        Returns:
            BacktestResult with complete results
        """
        if not market_data:
            raise ValueError("No market data provided")
        
        if not self.strategy:
            raise ValueError("No strategy callback set")
        
        logger.info(f"Starting backtest with {len(market_data)} candles")
        
        # Initialize
        self.is_running = True
        self.total_candles = len(market_data)
        self.total_ticks = len(market_data)  # Each candle is one tick
        self.processed_candles = 0
        self.processed_ticks = 0
        self.current_tick = 0
        start_time = time.time()
        
        # Sort market data by timestamp
        market_data.sort(key=lambda c: c.timestamp)
        
        # Process each candle
        with tqdm(total=len(market_data), desc="Backtesting") as pbar:
            for candle in market_data:
                if not self.is_running:
                    logger.info("Backtest stopped by user")
                    break
                
                self._process_candle(candle)
                self.processed_candles += 1
                
                # Progress callback with tick information
                if self.progress_callback and self.processed_candles % 10 == 0: # Update every 10 candles
                    asyncio.run(self.progress_callback(self.get_status()))

                pbar.update(1)
        
        execution_time = time.time() - start_time
        
        # Generate results
        result = self._generate_results(
            market_data[0].timestamp,
            market_data[-1].timestamp,
            execution_time
        )
        
        logger.info(f"Backtest completed in {execution_time:.2f}s")

        # Final progress update
        if self.progress_callback:
            asyncio.run(self.progress_callback(self.get_status()))
        return result
    
    def _process_candle(self, candle: Candle) -> None:
        """
        Process single market data candle as one tick.
        
        Args:
            candle: Market data candle
        """
        # Update tick and time tracking
        self.current_tick += 1
        self.current_time = candle.timestamp
        
        logger.debug(f"Processing tick {self.current_tick}: {candle.timestamp} - Price: {candle.close}")
        
        # Update portfolio with new prices
        self.portfolio.update_prices(candle)
        
        # Process tick-based order fills
        self._process_tick_orders(candle)
        
        # Call strategy with new tick data
        if self.strategy:
            try:
                self.strategy.on_bar(candle)
            except Exception as e:
                logger.error(f"Strategy error at tick {self.current_tick} ({candle.timestamp}): {e}")
        
        # Process any new orders submitted by strategy
        self._process_tick_orders(candle)
        
        # Process events
        self.event_queue.process_events()
        
        # Update processed ticks
        self.processed_ticks += 1
    
    def _process_tick_orders(self, candle: Candle) -> None:
        """
        Process order fills for the current tick against market data.
        
        Args:
            candle: Current market candle (representing one tick)
        """
        filled_or_cancelled_orders = []
        
        logger.debug(f"Processing {len(self.active_orders)} active orders for tick {self.current_tick}")
        
        for order_id, order in self.active_orders.items():
            if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                filled_or_cancelled_orders.append(order_id)
                continue
            
            # Skip orders that were just submitted in this same tick
            # to prevent immediate execution within the same tick
            if order.submitted_at and order.submitted_at >= candle.timestamp:
                logger.debug(f"Skipping order {order_id} - submitted in current tick")
                continue
            
            # Attempt to fill order on this tick
            fill_event = self.order_simulator.simulate_execution(
                order, candle
            )
            
            if fill_event:
                # Update order with fill details
                order.status = OrderStatus.FILLED
                order.avg_fill_price = fill_event.fill_price
                order.filled_at = self.current_time

                # Calculate commission
                commission = self._calculate_commission(
                    fill_event.fill_quantity,
                    fill_event.fill_price
                )
                fill_event.commission = commission
                
                # Execute against portfolio
                success = self.portfolio.execute_order(
                    order, fill_event.fill_price, commission
                )
                
                if success:
                    filled_or_cancelled_orders.append(order_id)
                    
                    # Add to order history for trade tracking
                    self.order_history.append(order)
                    
                    # Notify strategy of the fill
                    if self.strategy:
                        self.strategy.on_order_update(order)

                    # Create trade record if this completes a round trip
                    self._check_for_completed_trade(order, fill_event)
                    
                    logger.info(f"Tick {self.current_tick}: Order filled - {order.action.value} {order.quantity} {order.symbol} @ {fill_event.fill_price:.2f}")
                else:
                    order.status = OrderStatus.REJECTED # e.g. insufficient funds
                    filled_or_cancelled_orders.append(order_id)
                    logger.warning(f"Tick {self.current_tick}: Order rejected after fill attempt - {order.id}")
        
        # Remove filled/cancelled orders
        for order_id in filled_or_cancelled_orders:
            self.active_orders.pop(order_id, None)
        
        if filled_or_cancelled_orders:
            logger.debug(f"Tick {self.current_tick}: Processed {len(filled_or_cancelled_orders)} orders")
    
    def submit_order(self, order: Order) -> bool:
        """
        Public method to submit new order.
        
        Args:
            order: Order to submit
            
        Returns:
            True if order accepted
        """
        return self._submit_order(order)
    
    def get_current_tick(self) -> int:
        """
        Get current tick number.
        
        Returns:
            Current tick number
        """
        return self.current_tick
    
    def get_tick_info(self) -> Dict[str, Any]:
        """
        Get detailed tick information.
        
        Returns:
            Dictionary with tick information
        """
        return {
            'current_tick': self.current_tick,
            'total_ticks': self.total_ticks,
            'processed_ticks': self.processed_ticks,
            'tick_progress_pct': (self.processed_ticks / self.total_ticks * 100) if self.total_ticks > 0 else 0,
            'current_time': self.current_time.isoformat() if self.current_time else None,
            'active_orders_count': len(self.active_orders)
        }
    def _submit_order(self, order: Order) -> bool:
        """
        Submit new order.
        
        Args:
            order: Order to submit
            
        Returns:
            True if order accepted
        """
        try:
            # Validate order
            if not self._validate_order(order):
                logger.warning(f"Order validation failed: {order.id} - {order.action.value} {order.quantity} {order.symbol} @ {order.price or 'MARKET'}")
                order.status = OrderStatus.REJECTED
                return False
            
            # Update order status
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = self.current_time
            order.created_at = self.current_time
            
            # Add to active orders
            self.active_orders[order.id] = order
            
            # Queue order event
            # self.event_queue.put(OrderEvent(order, self.current_time))
            
            logger.debug(f"Order submitted: {order.action.value} {order.quantity} {order.symbol} @ {order.price if order.price else 'MARKET'}")
            return True

        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return False

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.

        Args:
            order_id: The ID of the order to cancel.

        Returns:
            True if the order was found and cancelled, False otherwise.
        """
        order = self.active_orders.get(order_id)
        if order and order.is_active:
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = self.current_time
            logger.debug(f"Order {order_id} cancelled by strategy.")

            # Notify strategy of the cancellation
            if self.strategy:
                self.strategy.on_order_update(order)

            # The order will be removed from active_orders in the next _process_order_fills cycle
            return True
        else:
            logger.warning(f"Attempted to cancel non-existent or inactive order: {order_id}")
            return False
    
    def _validate_order(self, order: Order) -> bool:
        """
        Validate order before submission.
        
        Args:
            order: Order to validate
            
        Returns:
            True if order is valid
        """
        # Basic validation
        if order.quantity <= 0:
            logger.debug(f"Order validation failed: quantity {order.quantity} <= 0")
            return False

        # Check for required price on limit orders
        if order.order_type == OrderType.LIMIT and order.price is None:
            logger.debug(f"Order validation failed: LIMIT order missing price")
            return False

        # Check cash for buy orders (simplified)
        if order.action == OrderAction.BUY:
            # For market orders, estimate using current market price
            if order.order_type == OrderType.MARKET:
                # Get current price from portfolio positions first
                current_price = 100.0  # Default fallback
                if hasattr(self.portfolio, 'positions') and order.symbol in self.portfolio.positions:
                    position = self.portfolio.positions[order.symbol]
                    if hasattr(position, 'last_price') and position.last_price > 0:
                        current_price = position.last_price
                
                estimated_cost = order.quantity * current_price
            else:
                # For limit orders, use the limit price
                estimated_cost = order.quantity * order.price
            
            if self.portfolio.cash < estimated_cost:
                logger.debug(f"Order validation failed: insufficient cash. Need {estimated_cost:.2f}, have {self.portfolio.cash:.2f}")
                return False
        
        logger.debug(f"Order validation passed: {order.action.value} {order.quantity} @ {order.price or 'MARKET'}")
        return True
    
    def _calculate_commission(self, quantity: float, price: float) -> float:
        """
        Calculate commission for trade.
        
        Args:
            quantity: Trade quantity
            price: Trade price
            
        Returns:
            Commission amount
        """
        trade_value = quantity * price
        
        # Percentage fee
        commission = trade_value * (self.config.backtest.fee_bps / 10000.0)
        
        # Fixed fee per trade
        commission += self.config.backtest.commission_per_trade
        
        return round(commission, 2)
    
    def _check_for_completed_trade(self, order: Order, fill_event: FillEvent) -> None:
        """
        Create trade records from filled orders.
        For individual orders, each filled order is recorded as a trade entry.
        
        Args:
            order: Completed order
            fill_event: Fill event
        """
        if order.status == OrderStatus.FILLED:
            # Calculate duration properly
            duration_seconds = 0.0
            if order.created_at and order.filled_at:
                duration_seconds = (order.filled_at - order.created_at).total_seconds()
            
            # Record each order execution as a "trade" for visualization purposes
            # In grid trading, each order execution is meaningful
            side = "BUY" if order.action == OrderAction.BUY else "SELL"
            
            # For display purposes, we'll show the order execution
            # PnL calculation would require pairing with opposite orders
            trade = Trade(
                id=order.id,  # Use order ID as trade ID for easier tracking
                symbol=order.symbol,
                entry_time=order.filled_at or self.current_time,
                exit_time=order.filled_at or self.current_time,  # Same time for individual orders
                entry_price=fill_event.fill_price,
                exit_price=fill_event.fill_price,
                quantity=fill_event.fill_quantity,
                side=side,  # Show actual side (BUY/SELL)
                pnl=0.0,  # Individual order has no PnL
                pnl_pct=0.0,
                fees=fill_event.commission,
                duration_seconds=duration_seconds
            )
            
            self.completed_trades.append(trade)
            
            logger.debug(f"Order execution recorded: {side} {fill_event.fill_quantity} {order.symbol} @ {fill_event.fill_price:.2f}")
    
    def _generate_results(
        self,
        start_time: datetime,
        end_time: datetime,
        execution_time: float
    ) -> BacktestResult:
        """
        Generate final backtest results.
        
        Args:
            start_time: Backtest start time
            end_time: Backtest end time
            execution_time: Execution time in seconds
            
        Returns:
            Complete BacktestResult
        """
        # Convert portfolio equity curve to EquityPoint objects
        equity_curve = []
        for point in self.portfolio.equity_curve:
            equity_point = EquityPoint(
                timestamp=point['timestamp'],
                equity=point['equity'],
                drawdown=point['drawdown'],
                drawdown_pct=point['drawdown_pct']
            )
            equity_curve.append(equity_point)
        
        # Calculate performance metrics
        metrics = self.metrics_calculator.calculate_metrics(
            initial_capital=self.config.backtest.initial_cash,
            final_capital=self.portfolio.total_equity,
            equity_curve=equity_curve,
            trades=self.completed_trades,
            start_date=start_time,
            end_date=end_time
        )
        
        # Convert active orders to list
        all_orders = list(self.active_orders.values())
        
        # Create result
        result = BacktestResult(
            run_id=self.run_id,
            symbol=self.config.data.symbol,
            exchange=self.config.data.exchange,
            start_time=start_time,
            end_time=end_time,
            config=self.config.to_dict(),
            trades=self.completed_trades,
            orders=all_orders,
            equity_curve=equity_curve,
            metrics=metrics,
            total_candles=self.total_candles,
            execution_time=execution_time
        )
        
        return result
    
    def stop(self) -> None:
        """Stop the backtest."""
        self.is_running = False
        logger.info("Backtest stop requested")
    
    def set_progress_callback(self, callback: Callable):
        """Set an async callback for progress updates."""
        self.progress_callback = callback

    def get_status(self) -> Dict[str, Any]:
        """
        Get current backtest status including tick information.
        
        Returns:
            Status dictionary
        """
        return {
            'run_id': self.run_id,
            'is_running': self.is_running,
            'current_time': self.current_time.isoformat() if self.current_time else None,
            'current_tick': self.current_tick,
            'total_candles': self.total_candles,
            'processed_candles': self.processed_candles,
            'total_ticks': self.total_ticks,
            'processed_ticks': self.processed_ticks,
            'progress_pct': (self.processed_candles / self.total_candles * 100) if self.total_candles > 0 else 0,
            'tick_progress_pct': (self.processed_ticks / self.total_ticks * 100) if self.total_ticks > 0 else 0,
            'active_orders': len(self.active_orders),
            'completed_trades': len(self.completed_trades),
            'current_equity': self.portfolio.total_equity,
            'current_pnl': self.portfolio.total_pnl
        }
