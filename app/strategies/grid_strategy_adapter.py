# app/strategies/grid_strategy_adapter.py
"""
Adapter to wrap the existing GridTradingBot for use in the backtesting engine.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from strats.grid_trading_bot import GridTradingBot
from .base_strategy import BaseStrategy
from ..models.market_data import Candle
from ..models.orders import Order, OrderAction, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class MockOpenAlgoClient:
    """
A mock of the OpenAlgo client to intercept API calls from the GridTradingBot
and route them through the backtesting engine.
"""

    def __init__(self, adapter: 'GridStrategyAdapter'):
        self._adapter = adapter
        self.order_id_counter = 1

    def quotes(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """Simulate fetching the latest quote."""
        if self._adapter.current_bar:
            return {
                'status': 'success',
                'data': {'ltp': self._adapter.current_bar.close}
            }
        return {'status': 'error', 'message': 'No current bar data'}

    def placeorder(self, **kwargs) -> Dict[str, Any]:
        """Capture an order placement and send it to the backtest engine."""
        action = OrderAction.BUY if kwargs.get('action') == 'BUY' else OrderAction.SELL
        price_type = kwargs.get('price_type', 'LIMIT')
        quantity = int(kwargs.get('quantity', 0))
        price = float(kwargs.get('price', 0.0))

        if price_type == 'LIMIT':
            order_type = OrderType.LIMIT
        elif price_type == 'MARKET':
            order_type = OrderType.MARKET
        else:
            logger.error(f"Unsupported order type from grid bot: {price_type}")
            return {'status': 'error', 'message': 'Unsupported order type'}

        if quantity <= 0:
            logger.error(f"Invalid order quantity from grid bot: {quantity}")
            return {'status': 'error', 'message': 'Invalid quantity'}

        # Create a unique client order ID for the bot
        client_order_id = str(uuid.uuid4())

        order = Order(
            id=client_order_id,
            symbol=self._adapter.bot.symbol,
            exchange=self._adapter.bot.exchange,
            action=action,
            order_type=order_type,
            quantity=quantity,
            price=price if order_type == OrderType.LIMIT else None
        )

        logger.info(
            f"Adapter: Intercepted order from bot. Submitting to engine: "
            f"{order.action.value} {order.quantity} {order.symbol} @ {order.price or 'MARKET'}"
        )
        # Submit the order via the adapter's context
        self._adapter.submit_order(order)

        # The bot expects an order ID back. We use our client_order_id.
        return {'status': 'success', 'orderid': client_order_id}

    def cancelallorder(self, strategy: str) -> Dict[str, Any]:
        """Simulate canceling all orders for the strategy."""
        cancelled_ids = self._adapter.cancel_all_orders()
        logger.info(f"Adapter: Intercepted 'cancel all'. Canceled {len(cancelled_ids)} orders in engine.")
        return {
            'status': 'success',
            'canceled_orders': cancelled_ids
        }

    def orderbook(self) -> Dict[str, Any]:
        """
        Simulate the order book by checking the status of orders submitted
by the bot.
        """
        logger.info("Adapter: Bot is requesting order book.")
        orders_from_engine = self._adapter.get_orders()
        
        bot_orders = []
        
        # First, add all active orders from engine
        for order in orders_from_engine:
            if order.id:
                status_map = {
                    OrderStatus.PENDING: 'open',
                    OrderStatus.SUBMITTED: 'open',  # Add this missing mapping
                    OrderStatus.FILLED: 'complete',
                    OrderStatus.CANCELLED: 'cancelled',
                    OrderStatus.REJECTED: 'rejected',
                }
                mapped_status = status_map.get(order.status, 'unknown')
                logger.debug(f"Adapter: Order {order.id} - Status: {order.status} -> {mapped_status}, Price: {order.avg_fill_price or order.price}")
                
                bot_orders.append({
                    'orderid': order.id,
                    'order_status': mapped_status,
                    'price': order.avg_fill_price or order.price or 0.0
                })

        # Add recent fills that the bot hasn't processed yet (these are removed from active_orders)
        for order_id, fill_info in list(self._adapter.recent_fills.items()):
            logger.debug(f"Adapter: Adding recent fill {order_id} - Status: complete, Price: {fill_info['price']}")
            bot_orders.append({
                'orderid': order_id,
                'order_status': 'complete',
                'price': fill_info['price']
            })

        logger.info(f"Adapter: Returning {len(bot_orders)} orders to bot")
        return {
            'status': 'success',
            'data': {'orders': bot_orders}
        }


class GridStrategyAdapter(BaseStrategy):
    """
Wraps the GridTradingBot to make it compatible with the backtesting engine.
"""

    def __init__(self):
        super().__init__("GridStrategyAdapter")
        self.bot: Optional[GridTradingBot] = None
        self.current_bar: Optional[Candle] = None
        self._initialized = False
        # Keep track of recently filled orders so bot can detect them
        self.recent_fills: Dict[str, Dict] = {}  # order_id -> fill_info

    def initialize(self, **params: Any):
        """
        Initializes the GridTradingBot with parameters and a mock client.
        """
        logger.info("Initializing GridStrategyAdapter...")

        # The bot requires these, but they are not used in the backtest
        # as the mock client intercepts all API calls.
        dummy_api_key = "backtest-dummy-key"
        dummy_host = "http://mock-server"

        # Default to a safe initial position strategy for backtesting
        initial_pos_strat = params.get('initial_position_strategy', 'wait_for_buy')

        self.bot = GridTradingBot(
            api_key=dummy_api_key,
            host=dummy_host,
            symbol=params.get('symbol', 'RELIANCE'),
            exchange=params.get('exchange', 'NSE'),
            grid_levels=params.get('grid_levels', 10),
            grid_spacing_pct=params.get('grid_spacing_pct', 1.0),
            order_amount=params.get('order_amount', 1000),
            grid_type=params.get('grid_type', 'arithmetic'),
            stop_loss_pct=params.get('stop_loss_pct', 5.0),
            take_profit_pct=params.get('take_profit_pct', 10.0),
            auto_reset=params.get('auto_reset', True),
            state_file='grid_state_backtest.json', # Use a different state file
            initial_position_strategy=initial_pos_strat
        )

        # Replace the live client with our mock client
        self.bot.client = MockOpenAlgoClient(self)

        # The bot's internal logging can be noisy; set to a higher level if needed
        self.bot.logger.setLevel(logging.INFO)

        logger.info("GridTradingBot instance created for backtesting.")

    def on_bar(self, candle: Candle):
        """
        Called by the backtest engine for each new bar of data.
        """
        if not self.bot:
            logger.error("Strategy not initialized. Call initialize() first.")
            return

        self.current_bar = candle

        # First run: set up the grid
        if not self._initialized:
            logger.info(f"Setting up initial grid at price: {candle.close}")
            # The bot uses get_current_price() which is mocked to use self.current_bar
            if not self.bot.setup_grid():
                logger.error("Failed to set up initial grid for the bot.")
                # Potentially stop the backtest if setup fails
                return
            self._initialized = True

        # Main logic from the bot's loop, adapted for backtesting:
        # 1. Check for filled orders (mock client will report fills from the engine)
        filled_orders = self.bot.check_filled_orders()
        
        # Clear recent fills that were processed by the bot
        for filled_order in filled_orders:
            if filled_order['order_id'] in self.recent_fills:
                del self.recent_fills[filled_order['order_id']]
                logger.info(f"Adapter: Cleared processed fill {filled_order['order_id']}")

        # 2. Check grid bounds and handle breakouts
        bounds_status = self.bot.check_grid_bounds(candle.close)
        if bounds_status != 'within':
            self.bot.handle_breakout(candle.close, bounds_status)

        # The bot's internal state is now updated.
        # The mock client has already submitted any new/opposite orders to the engine.

    def on_order_update(self, order: Order):
        """
        Called by the backtest engine when an order's status changes.
        The bot's check_filled_orders() will pick this up on the next bar.
        """
        if not self.bot:
            return

        if order.status == OrderStatus.FILLED:
            logger.info(f"Adapter received fill for order {order.id} at {order.avg_fill_price}")
            # Store the fill info so the bot can detect it via orderbook()
            self.recent_fills[order.id] = {
                'price': order.avg_fill_price,
                'timestamp': datetime.now()
            }
        elif order.status == OrderStatus.CANCELLED:
            logger.debug(f"Adapter received cancel for order {order.id}")

        # No direct action needed here, as the bot's `check_filled_orders`
        # polls for status via the mocked `orderbook` method. This correctly
        # simulates the bot's original polling behavior.