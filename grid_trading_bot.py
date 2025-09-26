
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
import math
from typing import Dict, List, Optional, Tuple
from openalgo import api
import os

class GridTradingBot:
    """
    Advanced Grid Trading Strategy for OpenAlgo Platform

    Features:
    - Dynamic grid creation with configurable levels
    - Risk management with stop-loss and take-profit
    - Breakout handling and grid reset
    - Position tracking and state persistence
    - Multiple grid types (arithmetic/geometric)
    - Comprehensive logging and monitoring
    """

    def __init__(self,
                 api_key: str,
                 host: str = 'http://127.0.0.1:5000',
                 symbol: str = 'RELIANCE',
                 exchange: str = 'NSE',
                 grid_levels: int = 10,
                 grid_spacing_pct: float = 1.0,
                 order_amount: float = 1000,  # Amount per order in currency
                 grid_type: str = 'arithmetic',  # 'arithmetic' or 'geometric'
                 stop_loss_pct: float = 5.0,
                 take_profit_pct: float = 10.0,
                 auto_reset: bool = True,
                 state_file: str = 'grid_trading_state.json',
                 initial_position_strategy: str = 'wait_for_buy'):
        """
        Initialize Grid Trading Bot

        Args:
            api_key: OpenAlgo API key
            host: OpenAlgo server URL
            symbol: Trading symbol
            exchange: Exchange name
            grid_levels: Number of grid levels (total = 2 * grid_levels)
            grid_spacing_pct: Percentage spacing between grid levels
            order_amount: Amount to invest per grid order
            grid_type: 'arithmetic' (fixed spacing) or 'geometric' (percentage spacing)
            stop_loss_pct: Stop loss percentage from grid center
            take_profit_pct: Take profit percentage from grid center
            auto_reset: Whether to automatically reset grid on breakout
            state_file: File to save trading state
            initial_position_strategy: 'wait_for_buy' or 'buy_at_market' - controls sell order placement
        """
        self.client = api(api_key=api_key, host=host)
        self.symbol = symbol
        self.exchange = exchange
        self.grid_levels = grid_levels
        self.grid_spacing_pct = grid_spacing_pct
        self.order_amount = order_amount
        self.grid_type = grid_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.auto_reset = auto_reset
        self.state_file = state_file
        self.initial_position_strategy = initial_position_strategy

        # Grid state variables
        self.grid_center_price = None
        self.grid_upper_bound = None
        self.grid_lower_bound = None
        self.buy_orders = {}  # {price: order_id}
        self.sell_orders = {}  # {price: order_id}
        self.filled_orders = []  # History of filled orders
        self.pending_orders = {}  # {order_id: order_details}

        # Performance tracking
        self.total_trades = 0
        self.total_profit = 0.0
        self.total_fees = 0.0
        self.grid_resets = 0
        self.current_position = 0  # Net position
        self.unrealized_pnl = 0.0

        # Risk management
        self.is_active = True
        self.last_price = None
        self.price_history = []

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'grid_trading_{symbol.lower()}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Load previous state
        self.load_state()

        self.logger.info(f"Initialized Grid Trading Bot for {symbol}")
        self.logger.info(f"Grid: {grid_levels} levels, {grid_spacing_pct}% spacing, {grid_type} type")

    def get_current_price(self) -> Optional[float]:
        """Get current market price"""
        try:
            response = self.client.quotes(symbol=self.symbol, exchange=self.exchange)
            if response.get('status') == 'success':
                price = float(response['data']['ltp'])
                self.last_price = price
                self.price_history.append({'timestamp': datetime.now(), 'price': price})

                # Keep only last 1000 price points
                if len(self.price_history) > 1000:
                    self.price_history = self.price_history[-1000:]

                return price
            else:
                self.logger.error(f"Error getting quote: {response}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return None

    def calculate_grid_levels(self, center_price: float) -> Tuple[List[float], List[float]]:
        """
        Calculate buy and sell grid levels

        Args:
            center_price: Center price for grid

        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        buy_levels = []
        sell_levels = []

        if self.grid_type == 'arithmetic':
            # Fixed price intervals
            spacing = center_price * (self.grid_spacing_pct / 100)

            for i in range(1, self.grid_levels + 1):
                buy_price = center_price - (spacing * i)
                sell_price = center_price + (spacing * i)

                if buy_price > 0:  # Ensure positive prices
                    buy_levels.append(round(buy_price, 2))
                sell_levels.append(round(sell_price, 2))

        elif self.grid_type == 'geometric':
            # Percentage-based intervals
            ratio = 1 + (self.grid_spacing_pct / 100)

            for i in range(1, self.grid_levels + 1):
                buy_price = center_price / (ratio ** i)
                sell_price = center_price * (ratio ** i)

                buy_levels.append(round(buy_price, 2))
                sell_levels.append(round(sell_price, 2))

        # Sort levels
        buy_levels.sort(reverse=True)  # Highest buy price first
        sell_levels.sort()  # Lowest sell price first

        return buy_levels, sell_levels

    def setup_grid(self, center_price: Optional[float] = None) -> bool:
        """
        Setup initial grid with buy and sell orders

        Args:
            center_price: Center price for grid (uses current price if None)

        Returns:
            True if setup successful, False otherwise
        """
        try:
            if center_price is None:
                center_price = self.get_current_price()
                if center_price is None:
                    return False

            self.grid_center_price = center_price

            # Calculate grid bounds for risk management
            self.grid_upper_bound = center_price * (1 + self.take_profit_pct / 100)
            self.grid_lower_bound = center_price * (1 - self.stop_loss_pct / 100)

            # Calculate grid levels
            buy_levels, sell_levels = self.calculate_grid_levels(center_price)

            self.logger.info(f"Setting up grid around ${center_price:.2f}")
            self.logger.info(f"Grid bounds: ${self.grid_lower_bound:.2f} - ${self.grid_upper_bound:.2f}")
            self.logger.info(f"Buy levels: {len(buy_levels)}, Sell levels: {len(sell_levels)}")

            # Cancel existing orders before placing new ones
            self.cancel_all_orders()

            # Calculate order quantity based on order amount and price
            success_count = 0

            # Place buy orders
            for price in buy_levels:
                if price > self.grid_lower_bound:  # Only place orders within bounds
                    quantity = math.floor(self.order_amount / price)
                    if quantity > 0:
                        order_id = self.place_limit_order('BUY', quantity, price)
                        if order_id:
                            self.buy_orders[price] = order_id
                            self.pending_orders[order_id] = {
                                'type': 'BUY',
                                'price': price,
                                'quantity': quantity,
                                'timestamp': datetime.now()
                            }
                            success_count += 1

            # Place sell orders based on initial position strategy
            if self.initial_position_strategy == 'buy_at_market':
                # First buy shares at market price to cover sell orders
                if sell_levels and self.buy_initial_shares_at_market(sell_levels):
                    # Now place sell orders since we have shares
                    for price in sell_levels:
                        if price < self.grid_upper_bound:  # Only place orders within bounds
                            quantity = math.floor(self.order_amount / price)
                            if quantity > 0:
                                order_id = self.place_limit_order('SELL', quantity, price)
                                if order_id:
                                    self.sell_orders[price] = order_id
                                    self.pending_orders[order_id] = {
                                        'type': 'SELL',
                                        'price': price,
                                        'quantity': quantity,
                                        'timestamp': datetime.now()
                                    }
                                    success_count += 1
                else:
                    self.logger.warning("Failed to buy initial shares at market - no sell orders placed")
                    
            elif self.initial_position_strategy == 'wait_for_buy':
                # Only place sell orders if we have sufficient position
                available_shares = self.current_position
                self.logger.info(f"Current position: {available_shares} shares")
                self.logger.info(f"Wait_for_buy strategy: Will only place sell orders after acquiring shares through buy orders")
                
                if available_shares > 0:
                    # Place sell orders only for shares we have
                    shares_allocated = 0
                    for price in sell_levels:
                        if price < self.grid_upper_bound:  # Only place orders within bounds
                            quantity = math.floor(self.order_amount / price)
                            
                            # Check if we have enough shares for this sell order
                            if shares_allocated + quantity <= available_shares:
                                order_id = self.place_limit_order('SELL', quantity, price)
                                if order_id:
                                    self.sell_orders[price] = order_id
                                    self.pending_orders[order_id] = {
                                        'type': 'SELL',
                                        'price': price,
                                        'quantity': quantity,
                                        'timestamp': datetime.now()
                                    }
                                    shares_allocated += quantity
                                    success_count += 1
                            else:
                                self.logger.info(f"Skipping sell order at {price} - insufficient shares (need {quantity}, have {available_shares - shares_allocated} available)")
                    
                    if shares_allocated < available_shares:
                        self.logger.info(f"Not all shares allocated to sell orders. {available_shares - shares_allocated} shares remaining")
                else:
                    self.logger.info("No shares in position - no sell orders placed. Sell orders will be placed after buy orders are filled.")
            else:
                # Fallback to original behavior for backward compatibility
                for price in sell_levels:
                    if price < self.grid_upper_bound:  # Only place orders within bounds
                        quantity = math.floor(self.order_amount / price)
                        if quantity > 0:
                            order_id = self.place_limit_order('SELL', quantity, price)
                            if order_id:
                                self.sell_orders[price] = order_id
                                self.pending_orders[order_id] = {
                                    'type': 'SELL',
                                    'price': price,
                                    'quantity': quantity,
                                    'timestamp': datetime.now()
                                }
                                success_count += 1

            self.logger.info(f"Grid setup complete: {success_count} orders placed")
            return success_count > 0

        except Exception as e:
            self.logger.error(f"Error setting up grid: {e}")
            return False

    def place_limit_order(self, action: str, quantity: int, price: float) -> Optional[str]:
        """
        Place limit order via OpenAlgo

        Args:
            action: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Limit price

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            response = self.client.placeorder(
                strategy="GridTrading",
                symbol=self.symbol,
                action=action,
                exchange=self.exchange,
                price_type="LIMIT",
                product="MIS",
                quantity=quantity,
                price=str(price),
                trigger_price="0",
                disclosed_quantity="0"
            )

            if response.get('status') == 'success':
                order_id = response.get('orderid')
                self.logger.debug(f"Placed {action} order: {quantity} @ {price} - ID: {order_id}")
                return order_id
            else:
                self.logger.error(f"Order failed: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error placing {action} order: {e}")
            return None

    def place_market_order(self, action: str, quantity: int) -> Optional[str]:
        """
        Place market order via OpenAlgo

        Args:
            action: 'BUY' or 'SELL'
            quantity: Order quantity

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            response = self.client.placeorder(
                strategy="GridTrading",
                symbol=self.symbol,
                action=action,
                exchange=self.exchange,
                price_type="MARKET",
                product="MIS",
                quantity=quantity,
                price="0",
                trigger_price="0",
                disclosed_quantity="0"
            )

            if response.get('status') == 'success':
                order_id = response.get('orderid')
                self.logger.info(f"Placed {action} market order: {quantity} shares - ID: {order_id}")
                return order_id
            else:
                self.logger.error(f"Market order failed: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error placing {action} market order: {e}")
            return None

    def buy_initial_shares_at_market(self, sell_levels: List[float]) -> bool:
        """
        Buy shares at market price to cover all sell orders

        Args:
            sell_levels: List of sell prices

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate total shares needed for all sell orders
            total_shares_needed = 0
            for price in sell_levels:
                quantity = math.floor(self.order_amount / price)
                total_shares_needed += quantity

            if total_shares_needed <= 0:
                return True

            current_price = self.get_current_price()
            if current_price is None:
                self.logger.error("Unable to get current price for market buy")
                return False

            self.logger.info(f"Buying {total_shares_needed} shares at market price {current_price:.2f} to cover sell orders")
            
            order_id = self.place_market_order('BUY', total_shares_needed)
            if order_id:
                # Update position immediately (assuming market order fills)
                # Note: In production, you should check order status
                self.current_position += total_shares_needed
                
                # Record the market buy transaction
                self.filled_orders.append({
                    'order_id': order_id,
                    'type': 'BUY',
                    'action': 'MARKET_BUY',
                    'quantity': total_shares_needed,
                    'price': current_price,
                    'timestamp': datetime.now(),
                    'purpose': 'initial_position'
                })
                
                self.logger.info(f"Successfully bought {total_shares_needed} shares. Current position: {self.current_position}")
                return True
            else:
                return False

        except Exception as e:
            self.logger.error(f"Error buying initial shares at market: {e}")
            return False

    def cancel_all_orders(self) -> int:
        """
        Cancel all pending orders

        Returns:
            Number of orders cancelled
        """
        try:
            response = self.client.cancelallorder(strategy="GridTrading")

            if response.get('status') == 'success':
                cancelled_count = len(response.get('canceled_orders', []))

                # Clear local order tracking
                self.buy_orders.clear()
                self.sell_orders.clear()
                self.pending_orders.clear()

                self.logger.info(f"Cancelled {cancelled_count} orders")
                return cancelled_count
            else:
                self.logger.error(f"Error cancelling orders: {response}")
                return 0

        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}")
            return 0

    def check_filled_orders(self) -> List[Dict]:
        """
        Check for filled orders and update grid

        Returns:
            List of newly filled orders
        """
        newly_filled = []

        try:
            # Get current order status
            response = self.client.orderbook()

            if response.get('status') == 'success':
                orders = response.get('data', {}).get('orders', [])

                for order in orders:
                    order_id = order.get('orderid')
                    status = order.get('order_status')

                    if order_id in self.pending_orders and status == 'complete':
                        order_details = self.pending_orders[order_id]

                        # Order was filled
                        filled_order = {
                            'order_id': order_id,
                            'type': order_details['type'],
                            'price': order_details['price'],
                            'quantity': order_details['quantity'],
                            'fill_price': float(order.get('price', order_details['price'])),
                            'timestamp': datetime.now()
                        }

                        newly_filled.append(filled_order)
                        self.filled_orders.append(filled_order)

                        # Remove from pending orders
                        del self.pending_orders[order_id]

                        # Remove from buy/sell orders
                        price = order_details['price']
                        if order_details['type'] == 'BUY' and price in self.buy_orders:
                            del self.buy_orders[price]
                        elif order_details['type'] == 'SELL' and price in self.sell_orders:
                            del self.sell_orders[price]

                        # Update position and profit
                        if order_details['type'] == 'BUY':
                            self.current_position += order_details['quantity']
                            self.logger.info(f"Buy order filled: position increased from {self.current_position - order_details['quantity']} to {self.current_position}")
                        else:
                            self.current_position -= order_details['quantity']
                            self.logger.info(f"Sell order filled: position decreased from {self.current_position + order_details['quantity']} to {self.current_position}")

                        self.total_trades += 1

                        # Place opposite order (grid refill)
                        self.place_opposite_order(filled_order)

                        self.logger.info(f"Order filled: {order_details['type']} {order_details['quantity']} @ {filled_order['fill_price']}")

        except Exception as e:
            self.logger.error(f"Error checking filled orders: {e}")

        return newly_filled

    def place_opposite_order(self, filled_order: Dict) -> bool:
        """
        Place opposite order after a fill to maintain grid

        Args:
            filled_order: Details of the filled order

        Returns:
            True if opposite order placed successfully
        """
        try:
            filled_type = filled_order['type']
            filled_price = filled_order['fill_price']
            quantity = filled_order['quantity']

            # Calculate opposite order price with profit margin
            if filled_type == 'BUY':
                # Place sell order above buy price
                opposite_price = filled_price * (1 + self.grid_spacing_pct / 100)
                opposite_action = 'SELL'
                
                # For wait_for_buy strategy, also place pending sell orders if we now have shares
                if self.initial_position_strategy == 'wait_for_buy' and self.current_position > 0:
                    self.logger.info(f"Buy order filled - attempting to place pending sell orders (position: {self.current_position})")
                    placed_orders = self.place_pending_sell_orders()
                    self.logger.info(f"Successfully placed {placed_orders} pending sell orders")
                    
            else:
                # Place buy order below sell price
                opposite_price = filled_price * (1 - self.grid_spacing_pct / 100)
                opposite_action = 'BUY'

            opposite_price = round(opposite_price, 2)

            # Check if price is within grid bounds
            if (opposite_action == 'BUY' and opposite_price < self.grid_lower_bound) or \
               (opposite_action == 'SELL' and opposite_price > self.grid_upper_bound):
                self.logger.warning(f"Opposite order price {opposite_price} outside grid bounds")
                return False

            # Place opposite order
            order_id = self.place_limit_order(opposite_action, quantity, opposite_price)

            if order_id:
                if opposite_action == 'BUY':
                    self.buy_orders[opposite_price] = order_id
                else:
                    self.sell_orders[opposite_price] = order_id

                self.pending_orders[order_id] = {
                    'type': opposite_action,
                    'price': opposite_price,
                    'quantity': quantity,
                    'timestamp': datetime.now()
                }

                self.logger.info(f"Placed opposite order: {opposite_action} {quantity} @ {opposite_price}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error placing opposite order: {e}")
            return False

    def place_pending_sell_orders(self) -> int:
        """
        Place sell orders for available shares (used in wait_for_buy strategy)
        
        Returns:
            Number of sell orders placed
        """
        try:
            self.logger.info(f"place_pending_sell_orders called: strategy={self.initial_position_strategy}")
            
            if self.initial_position_strategy != 'wait_for_buy':
                self.logger.info("Not wait_for_buy strategy, skipping")
                return 0
                
            if self.current_position <= 0 or self.grid_center_price is None:
                self.logger.info(f"Cannot place sell orders: position={self.current_position}, grid_center={self.grid_center_price}")
                return 0
                
            # Calculate sell levels from current grid
            _, sell_levels = self.calculate_grid_levels(self.grid_center_price)
            self.logger.info(f"Calculated {len(sell_levels)} sell levels: {sell_levels[:5]}...")  # Show first 5
            
            # Track shares allocated to existing sell orders
            shares_in_sell_orders = 0
            existing_sell_prices = []
            for order_id, details in self.pending_orders.items():
                if details['type'] == 'SELL':
                    shares_in_sell_orders += details['quantity']
                    existing_sell_prices.append(details['price'])
                    
            self.logger.info(f"Existing sell orders at prices: {existing_sell_prices}")
            self.logger.info(f"Shares already in sell orders: {shares_in_sell_orders}")
                    
            available_shares = self.current_position - shares_in_sell_orders
            self.logger.info(f"Available shares for new sell orders: {available_shares}")
            
            if available_shares <= 0:
                self.logger.info("No available shares for sell orders")
                return 0
                
            orders_placed = 0
            shares_allocated = 0
            
            # Place sell orders for prices that don't already have orders
            for price in sell_levels:
                self.logger.debug(f"Checking sell level {price}: within_bounds={price < self.grid_upper_bound}, already_exists={price in self.sell_orders}")
                
                if price < self.grid_upper_bound and price not in self.sell_orders:
                    quantity = math.floor(self.order_amount / price)
                    self.logger.debug(f"Calculated quantity for price {price}: {quantity}")
                    
                    # Check if we have enough available shares
                    if shares_allocated + quantity <= available_shares:
                        order_id = self.place_limit_order('SELL', quantity, price)
                        if order_id:
                            self.sell_orders[price] = order_id
                            self.pending_orders[order_id] = {
                                'type': 'SELL',
                                'price': price,
                                'quantity': quantity,
                                'timestamp': datetime.now()
                            }
                            shares_allocated += quantity
                            orders_placed += 1
                            self.logger.info(f"Placed pending sell order: {quantity} @ {price}")
                        else:
                            self.logger.warning(f"Failed to place sell order at {price}")
                    else:
                        self.logger.info(f"Insufficient shares for sell order at {price}: need {quantity}, have {available_shares - shares_allocated} available")
                        break  # No more shares available
                        
            if orders_placed > 0:
                self.logger.info(f"Placed {orders_placed} pending sell orders using {shares_allocated} shares")
            else:
                self.logger.warning("No pending sell orders were placed")
                
            return orders_placed
            
        except Exception as e:
            self.logger.error(f"Error placing pending sell orders: {e}")
            return 0

    def check_grid_bounds(self, current_price: float) -> str:
        """
        Check if current price is within grid bounds

        Args:
            current_price: Current market price

        Returns:
            'within', 'above', or 'below'
        """
        if current_price > self.grid_upper_bound:
            return 'above'
        elif current_price < self.grid_lower_bound:
            return 'below'
        else:
            return 'within'

    def handle_breakout(self, current_price: float, direction: str) -> bool:
        """
        Handle price breakout from grid bounds

        Args:
            current_price: Current market price
            direction: 'above' or 'below'

        Returns:
            True if breakout handled successfully
        """
        try:
            self.logger.warning(f"Grid breakout detected: Price {current_price} is {direction} bounds")

            if not self.auto_reset:
                self.logger.info("Auto-reset disabled, stopping bot")
                self.is_active = False
                return False

            # Close all positions and cancel orders
            self.cancel_all_orders()

            # Calculate profit/loss from current position
            if self.current_position != 0:
                position_value = self.current_position * current_price
                self.logger.info(f"Current position value: {position_value:.2f}")

            # Reset grid around new price
            self.grid_resets += 1
            self.logger.info(f"Resetting grid #{self.grid_resets} around ${current_price:.2f}")

            success = self.setup_grid(current_price)

            if success:
                self.logger.info("Grid reset successful")
            else:
                self.logger.error("Grid reset failed")
                self.is_active = False

            return success

        except Exception as e:
            self.logger.error(f"Error handling breakout: {e}")
            return False

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L from current positions

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L
        """
        if self.current_position == 0:
            return 0.0

        # Calculate average entry price from filled orders
        total_cost = 0.0
        total_quantity = 0

        for order in self.filled_orders:
            if order['type'] == 'BUY':
                total_cost += order['fill_price'] * order['quantity']
                total_quantity += order['quantity']
            else:
                total_cost -= order['fill_price'] * order['quantity']
                total_quantity -= order['quantity']

        if total_quantity == 0:
            return 0.0

        avg_price = total_cost / total_quantity if total_quantity != 0 else current_price
        unrealized_pnl = (current_price - avg_price) * self.current_position

        return unrealized_pnl

    def get_performance_summary(self) -> Dict:
        """
        Get comprehensive performance summary

        Returns:
            Dictionary with performance metrics
        """
        current_price = self.get_current_price() or 0
        unrealized_pnl = self.calculate_unrealized_pnl(current_price)

        # Calculate realized P&L
        realized_pnl = 0.0
        buy_orders = [o for o in self.filled_orders if o['type'] == 'BUY']
        sell_orders = [o for o in self.filled_orders if o['type'] == 'SELL']

        # Simple P&L calculation (can be improved with FIFO/LIFO)
        for sell in sell_orders:
            for buy in buy_orders:
                if buy['quantity'] > 0:
                    traded_qty = min(sell['quantity'], buy['quantity'])
                    pnl = (sell['fill_price'] - buy['fill_price']) * traded_qty
                    realized_pnl += pnl
                    buy['quantity'] -= traded_qty
                    sell['quantity'] -= traded_qty
                    if sell['quantity'] == 0:
                        break

        # Handle case where grid bounds might be None (not initialized yet)
        if self.grid_lower_bound is not None and self.grid_upper_bound is not None:
            grid_bounds_str = f"{self.grid_lower_bound:.2f} - {self.grid_upper_bound:.2f}"
        else:
            grid_bounds_str = "Not set"
        
        return {
            'symbol': self.symbol,
            'grid_center_price': self.grid_center_price,
            'current_price': current_price,
            'grid_bounds': grid_bounds_str,
            'total_trades': self.total_trades,
            'grid_resets': self.grid_resets,
            'current_position': self.current_position,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl,
            'active_buy_orders': len(self.buy_orders),
            'active_sell_orders': len(self.sell_orders),
            'is_active': self.is_active,
            'grid_type': self.grid_type,
            'grid_levels': self.grid_levels,
            'spacing_pct': self.grid_spacing_pct
        }

    def save_state(self):
        """Save current trading state to file"""
        state = {
            'grid_center_price': self.grid_center_price,
            'grid_upper_bound': self.grid_upper_bound,
            'grid_lower_bound': self.grid_lower_bound,
            'buy_orders': self.buy_orders,
            'sell_orders': self.sell_orders,
            'filled_orders': [
                {**order, 'timestamp': order['timestamp'].isoformat()}
                for order in self.filled_orders
            ],
            'pending_orders': {
                oid: {**details, 'timestamp': details['timestamp'].isoformat()}
                for oid, details in self.pending_orders.items()
            },
            'total_trades': self.total_trades,
            'total_profit': self.total_profit,
            'grid_resets': self.grid_resets,
            'current_position': self.current_position,
            'is_active': self.is_active,
            'last_update': datetime.now().isoformat()
        }

        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            self.logger.debug("State saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

    def load_state(self):
        """Load trading state from file"""
        if not os.path.exists(self.state_file):
            self.logger.info("No previous state file found, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            self.grid_center_price = state.get('grid_center_price')
            self.grid_upper_bound = state.get('grid_upper_bound')
            self.grid_lower_bound = state.get('grid_lower_bound')
            self.buy_orders = state.get('buy_orders', {})
            self.sell_orders = state.get('sell_orders', {})
            self.total_trades = state.get('total_trades', 0)
            self.total_profit = state.get('total_profit', 0.0)
            self.grid_resets = state.get('grid_resets', 0)
            self.current_position = state.get('current_position', 0)
            self.is_active = state.get('is_active', True)

            # Restore filled orders
            self.filled_orders = []
            for order in state.get('filled_orders', []):
                order['timestamp'] = datetime.fromisoformat(order['timestamp'])
                self.filled_orders.append(order)

            # Restore pending orders
            self.pending_orders = {}
            for oid, details in state.get('pending_orders', {}).items():
                details['timestamp'] = datetime.fromisoformat(details['timestamp'])
                self.pending_orders[oid] = details

            self.logger.info(f"State loaded: {self.total_trades} trades, Position: {self.current_position}")

        except Exception as e:
            self.logger.error(f"Error loading state: {e}")

    def run_grid_strategy(self, check_interval: int = 30):
        """
        Main strategy execution loop

        Args:
            check_interval: Time between checks in seconds
        """
        self.logger.info("Starting Grid Trading Strategy")
        self.logger.info(f"Check interval: {check_interval} seconds")

        # Setup initial grid if not already setup
        if self.grid_center_price is None:
            current_price = self.get_current_price()
            if current_price:
                if not self.setup_grid(current_price):
                    self.logger.error("Failed to setup initial grid")
                    return

        while self.is_active:
            try:
                current_time = datetime.now()

                # Skip if market is closed (basic check)
                if current_time.hour < 9 or current_time.hour >= 16:
                    self.logger.debug("Market closed, waiting...")
                    time.sleep(check_interval)
                    continue

                # Get current price
                current_price = self.get_current_price()
                if current_price is None:
                    self.logger.warning("Could not get current price")
                    time.sleep(check_interval)
                    continue

                # Check for filled orders
                filled_orders = self.check_filled_orders()
                if filled_orders:
                    for order in filled_orders:
                        self.logger.info(f"Grid order filled: {order['type']} {order['quantity']} @ {order['fill_price']}")

                # Check if price is within grid bounds
                bounds_status = self.check_grid_bounds(current_price)

                if bounds_status != 'within':
                    self.handle_breakout(current_price, bounds_status)

                # Log current status
                summary = self.get_performance_summary()
                self.logger.info(f"Price: ${current_price:.2f}, Position: {summary['current_position']}, "
                               f"P&L: {summary['total_pnl']:.2f}, Active Orders: {len(self.pending_orders)}")

                # Save state
                self.save_state()

                # Wait for next check
                time.sleep(check_interval)

            except KeyboardInterrupt:
                self.logger.info("Grid strategy stopped by user")
                self.is_active = False
                break
            except Exception as e:
                self.logger.error(f"Error in strategy loop: {e}")
                time.sleep(check_interval)

        # Final cleanup
        self.save_state()
        self.logger.info("Grid trading strategy stopped")

    def _find_order_at_price(self, level_price: float, order_book: Dict) -> Optional[str]:
        """
        Find an order ID for a given price level with a small tolerance.
        
        Args:
            level_price: The price of the grid level.
            order_book: The dictionary of orders to search (e.g., self.buy_orders).
        
        Returns:
            The order ID if found, otherwise None.
        """
        for price_str, oid in order_book.items():
            if abs(float(price_str) - level_price) < 0.01:
                return oid
        return None

    def get_trading_data_for_export(self) -> Dict:
        """
        Get comprehensive trading data for web dashboard export
        
        Returns:
            Dictionary with all trading data formatted for web display
        """
        current_price = self.get_current_price() or 0
        
        # Format price history for charts
        price_history = []
        for entry in self.price_history:
            price_history.append({
                'timestamp': entry['timestamp'].isoformat() if hasattr(entry['timestamp'], 'isoformat') else str(entry['timestamp']),
                'price': entry['price']
            })
        
        # Format filled orders with P&L calculation
        filled_orders_detailed = []
        for order in self.filled_orders:
            filled_orders_detailed.append({
                'order_id': order.get('order_id', 'N/A'),
                'timestamp': order['timestamp'].isoformat() if hasattr(order['timestamp'], 'isoformat') else str(order['timestamp']),
                'type': order['type'],
                'quantity': order['quantity'],
                'fill_price': order['fill_price'],
                'amount': order['quantity'] * order['fill_price'],
                'symbol': self.symbol
            })
        
        # Calculate grid levels with detailed info
        grid_levels = []
        if self.grid_center_price and self.grid_upper_bound and self.grid_lower_bound:
            if self.grid_type == 'arithmetic':
                spacing = (self.grid_upper_bound - self.grid_lower_bound) / (2 * self.grid_levels)
                for i in range(-self.grid_levels, self.grid_levels + 1):
                    level_price = self.grid_center_price + (i * spacing)
                    level_type = 'CENTER' if i == 0 else ('BUY' if i < 0 else 'SELL')
                    
                    order_book = self.buy_orders if level_type == 'BUY' else self.sell_orders
                    order_id = self._find_order_at_price(level_price, order_book) if level_type != 'CENTER' else None
                    grid_levels.append({
                        'price': level_price,
                        'type': level_type,
                        'level': i,
                        'has_order': has_order,
                        'order_id': order_id,
                        'distance_from_current': abs(level_price - current_price) / current_price * 100
                    })
            else:  # geometric
                for i in range(-self.grid_levels, self.grid_levels + 1):
                    multiplier = (1 + self.grid_spacing_pct / 100) ** i
                    level_price = self.grid_center_price * multiplier
                    level_type = 'CENTER' if i == 0 else ('BUY' if i < 0 else 'SELL')
                    
                    order_book = self.buy_orders if level_type == 'BUY' else self.sell_orders
                    order_id = self._find_order_at_price(level_price, order_book) if level_type != 'CENTER' else None
                    grid_levels.append({
                        'price': level_price,
                        'type': level_type,
                        'level': i,
                        'has_order': has_order,
                        'order_id': order_id,
                        'distance_from_current': abs(level_price - current_price) / current_price * 100
                    })
        
        # Calculate performance metrics over time
        performance_timeline = []
        cumulative_pnl = 0.0
        
        for order in sorted(self.filled_orders, key=lambda x: x['timestamp']):
            if order['type'] == 'SELL':
                # Simplified P&L calculation for visualization
                # In reality, this would match with specific buy orders
                cumulative_pnl += (order['fill_price'] * order['quantity'] * 0.002)  # Rough estimate
            else:  # BUY
                cumulative_pnl -= (order['fill_price'] * order['quantity'] * 0.001)  # Cost
            
            performance_timeline.append({
                'timestamp': order['timestamp'].isoformat() if hasattr(order['timestamp'], 'isoformat') else str(order['timestamp']),
                'cumulative_pnl': cumulative_pnl,
                'trade_type': order['type'],
                'trade_amount': order['fill_price'] * order['quantity']
            })
        
        # Risk metrics
        risk_metrics = {
            'max_position_value': abs(self.current_position) * current_price,
            'grid_utilization': len([o for o in self.buy_orders.values() if o]) + len([o for o in self.sell_orders.values() if o]),
            'max_grid_utilization': self.grid_levels * 2,
            'distance_from_stop_loss': abs(current_price - (self.grid_center_price * (1 - self.stop_loss_pct / 100))) / current_price * 100 if self.grid_center_price else 0,
            'distance_from_take_profit': abs(current_price - (self.grid_center_price * (1 + self.take_profit_pct / 100))) / current_price * 100 if self.grid_center_price else 0
        }
        
        return {
            'summary': self.get_performance_summary(),
            'price_history': price_history,
            'filled_orders': filled_orders_detailed,
            'grid_levels': grid_levels,
            'performance_timeline': performance_timeline,
            'risk_metrics': risk_metrics,
            'configuration': {
                'symbol': self.symbol,
                'exchange': self.exchange,
                'grid_levels': self.grid_levels,
                'grid_spacing_pct': self.grid_spacing_pct,
                'grid_type': self.grid_type,
                'order_amount': self.order_amount,
                'stop_loss_pct': self.stop_loss_pct,
                'take_profit_pct': self.take_profit_pct,
                'auto_reset': self.auto_reset
            }
        }


# Example usage and configuration
def main():
    """
    Example usage of the Grid Trading Bot
    """
    # Configuration
    config = {
        'api_key': '89fd8eaa346fb5e91bcbe8a3490b3d7b9c9c7defbe2babefd3037f11a41376a7',  # Replace with actual API key
        'host': 'http://127.0.0.1:5000',
        'symbol': 'IDFCFIRSTB',
        'exchange': 'NSE',
        'grid_levels': 7,                   # 7 levels above and below = 14 total orders
        'grid_spacing_pct': 1.5,            # 1.5% spacing between levels
        'order_amount': 500,               # ₹500 per grid order
        'grid_type': 'geometric',          # or 'arithmetic'
        'stop_loss_pct': 10.0,              # 10% stop loss from center
        'take_profit_pct': 15.0,            # 15% take profit from center
        'auto_reset': True,                  # Auto-reset grid on breakout
        'state_file': 'grid_trading_state.json'
    }

    # Initialize grid trading bot
    bot = GridTradingBot(**config)

    # Display current status
    summary = bot.get_performance_summary()
    print("Grid Trading Bot Status:")
    for key, value in summary.items():
        print(f"   {key}: {value}")

    # Run the strategy (uncomment to start trading)
    bot.run_grid_strategy(check_interval=30)  # Check every 30 seconds


if __name__ == "__main__":
    main()
