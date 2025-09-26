#!/usr/bin/env python3
"""
Test script to verify market order validation works correctly.
"""

import uuid
from datetime import datetime, timedelta
from app.models.config import AppConfig, BacktestConfig, DataConfig, OpenAlgoConfig, StrategyConfig, UIConfig, LoggingConfig
from app.models.market_data import Candle
from app.models.orders import Order, OrderAction, OrderType, OrderStatus
from app.core.backtest_engine import BacktestEngine
from app.strategies.base_strategy import BaseStrategy


class MarketOrderTestStrategy(BaseStrategy):
    """Test strategy to verify market order validation."""
    
    def __init__(self):
        super().__init__("MarketOrderTestStrategy")
        self.candle_count = 0
        self.orders_submitted = []
        self.orders_rejected = []
        self.orders_filled = []
    
    def initialize(self, **kwargs):
        self._initialized = True
    
    def on_bar(self, candle: Candle):
        self.candle_count += 1
        current_tick = self.context.get_current_tick() if self.context else 0
        
        print(f"Tick {current_tick} - Candle {self.candle_count}: Price = {candle.close:.2f}")
        
        # On first tick, place market orders
        if current_tick == 1:
            print(f"  Submitting market orders...")
            
            # Market buy order
            buy_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST",
                action=OrderAction.BUY,
                order_type=OrderType.MARKET,
                quantity=70,  # Same quantity as in the error log
                price=None   # Market orders have no price
            )
            
            # Market sell order
            sell_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST", 
                action=OrderAction.SELL,
                order_type=OrderType.MARKET,
                quantity=50,
                price=None
            )
            
            print(f"    Submitting BUY market order for {buy_order.quantity} shares")
            print(f"    Submitting SELL market order for {sell_order.quantity} shares")
            
            # Submit orders and track results
            buy_success = self.submit_order(buy_order)
            sell_success = self.submit_order(sell_order)
            
            if buy_success:
                self.orders_submitted.append(buy_order)
                print(f"    ✓ BUY market order accepted")
            else:
                self.orders_rejected.append(buy_order)
                print(f"    ✗ BUY market order rejected")
            
            if sell_success:
                self.orders_submitted.append(sell_order)
                print(f"    ✓ SELL market order accepted")
            else:
                self.orders_rejected.append(sell_order)
                print(f"    ✗ SELL market order rejected")
    
    def on_order_update(self, order: Order):
        if order.status == OrderStatus.FILLED:
            current_tick = self.context.get_current_tick() if self.context else 0
            self.orders_filled.append(order)
            print(f"  >> Tick {current_tick}: ORDER FILLED - {order.action.value} @ {order.avg_fill_price:.2f}")


def create_test_data():
    """Create test market data."""
    base_time = datetime.now()
    candles = []
    
    # Candle 1: Price = 63.11 (matching the error log)
    candles.append(Candle(
        symbol="IDFCFIRSTB",
        exchange="TEST", 
        timestamp=base_time,
        open=63.00,
        high=63.50,
        low=62.80,
        close=63.11,
        volume=1000
    ))
    
    # Candle 2: Price moves up slightly
    candles.append(Candle(
        symbol="IDFCFIRSTB",
        exchange="TEST",
        timestamp=base_time + timedelta(minutes=1),
        open=63.11,
        high=63.80,
        low=63.00,
        close=63.45,
        volume=1000
    ))
    
    return candles


def main():
    print("Testing Market Order Validation...")
    print("=" * 50)
    
    # Create configuration
    config = AppConfig(
        openalgo=OpenAlgoConfig(api_key="test"),
        data=DataConfig(
            symbol="IDFCFIRSTB", 
            exchange="TEST",
            start="2023-01-01",
            end="2023-01-02"
        ),
        backtest=BacktestConfig(
            initial_cash=10000.0,  # Should be enough for 70 shares @ ~63
            commission_per_trade=1.0,
            fee_bps=5.0,
            slippage_bps=2.0
        ),
        strategy=StrategyConfig(),
        ui=UIConfig(),
        logging=LoggingConfig()
    )
    
    # Create backtest engine
    engine = BacktestEngine(config)
    
    # Create and set strategy
    strategy = MarketOrderTestStrategy()
    strategy.initialize()
    engine.set_strategy(strategy)
    
    # Create test data
    market_data = create_test_data()
    
    print(f"Running test with initial cash: ₹{engine.portfolio.cash:.2f}")
    print("-" * 50)
    
    # Run backtest
    result = engine.run_backtest(market_data)
    
    # Analyze results
    print("\n" + "=" * 50)
    print("MARKET ORDER VALIDATION TEST RESULTS:")
    print("-" * 50)
    print(f"Orders submitted successfully: {len(strategy.orders_submitted)}")
    print(f"Orders rejected: {len(strategy.orders_rejected)}")
    print(f"Orders filled: {len(strategy.orders_filled)}")
    
    print(f"\nPortfolio status:")
    print(f"  Final cash: ₹{engine.portfolio.cash:.2f}")
    print(f"  Total equity: ₹{engine.portfolio.total_equity:.2f}")
    
    # Check results
    success = True
    if len(strategy.orders_rejected) > 0:
        print(f"\nFAIL: {len(strategy.orders_rejected)} market orders were rejected")
        success = False
    
    if len(strategy.orders_submitted) == 2:
        print("\nSUCCESS: Both market orders passed validation!")
    else:
        print(f"\nFAIL: Expected 2 submitted orders, got {len(strategy.orders_submitted)}")
        success = False
    
    return success


if __name__ == "__main__":
    main()