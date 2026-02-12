# app/strategies/mock_openalgo_client.py
"""
Common mock OpenAlgo client for use in strategy adapters during backtesting.
This mock intercepts API calls from trading bots and routes them through the backtesting engine.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import uuid
import pandas as pd

from ...models.orders import Order, OrderAction, OrderType, OrderStatus

if TYPE_CHECKING:
    from ..base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MockOpenAlgoClient:
    """
    A mock of the OpenAlgo client to intercept API calls from trading bots
    and route them through the backtesting engine.
    
    This class provides a common interface for both Grid and Supertrend strategy adapters.
    """

    def __init__(self, adapter: 'BaseStrategy'):
        self._adapter = adapter
        self.order_id_counter = 1

    def quotes(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """Simulate fetching the latest quote."""
        if hasattr(self._adapter, 'current_bar') and self._adapter.current_bar:
            return {
                'status': 'success',
                'data': {'ltp': self._adapter.current_bar.close}
            }
        return {'status': 'error', 'message': 'No current bar data'}

    def placeorder(self, **kwargs) -> Dict[str, Any]:
        """
        Capture an order placement and send it to the backtest engine.
        This method is used by GridTradingBot.
        """
        return self._place_order_common(**kwargs)

    def place_order(self, **kwargs) -> Dict[str, Any]:
        """
        Capture an order placement and send it to the backtest engine.
        This method is used by SupertrendTradingBot.
        """
        return self._place_order_common(**kwargs)

    def _place_order_common(self, **kwargs) -> Dict[str, Any]:
        """Common order placement logic for both grid and supertrend bots."""
        # Handle different action formats
        action_str = kwargs.get('action', '').upper()
        if action_str in ['BUY', 'buy']:
            action = OrderAction.BUY
        elif action_str in ['SELL', 'sell']:
            action = OrderAction.SELL
        else:
            logger.error(f"Invalid action from bot: {action_str}")
            return {'status': 'error', 'message': 'Invalid action'}

        # Handle different order type formats
        order_type_str = kwargs.get('price_type') or kwargs.get('order_type', 'MARKET')
        order_type_str = order_type_str.upper()
        
        quantity = int(kwargs.get('quantity', 0))
        price = kwargs.get('price', None)

        if order_type_str == 'LIMIT':
            order_type = OrderType.LIMIT
            price = float(price) if price is not None else None
        elif order_type_str == 'MARKET':
            order_type = OrderType.MARKET
            price = None
        else:
            logger.error(f"Unsupported order type from bot: {order_type_str}")
            return {'status': 'error', 'message': 'Unsupported order type'}

        if quantity <= 0:
            logger.error(f"Invalid order quantity from bot: {quantity}")
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
            price=price
        )

        logger.info(
            f"Mock Client: Intercepted order from bot. Submitting to engine: "
            f"{order.action.value} {order.quantity} {order.symbol} @ {order.price or 'MARKET'}"
        )
        
        # Submit the order via the adapter's context
        self._adapter.submit_order(order)

        # Return response in format expected by the bot
        response = {'status': 'success', 'orderid': client_order_id}
        
        # SupertrendTradingBot expects 'order_id' field as well
        if hasattr(self._adapter, 'bot') and 'SupertrendTradingBot' in str(type(self._adapter.bot)):
            response['order_id'] = client_order_id
            
        return response

    def cancelallorder(self, strategy: str = None) -> Dict[str, Any]:
        """
        Simulate canceling all orders for the strategy.
        This method is used by GridTradingBot.
        """
        return self._cancel_all_orders_common(strategy=strategy)

    def cancel_all_orders(self, symbol: str = None, exchange: str = None) -> Dict[str, Any]:
        """
        Simulate canceling all orders for the strategy.
        This method is used by SupertrendTradingBot.
        """
        return self._cancel_all_orders_common(symbol=symbol, exchange=exchange)

    def _cancel_all_orders_common(self, **kwargs) -> Dict[str, Any]:
        """Common order cancellation logic for both grid and supertrend bots."""
        cancelled_ids = self._adapter.cancel_all_orders()
        logger.info(f"Mock Client: Intercepted 'cancel all'. Canceled {len(cancelled_ids)} orders in engine.")
        return {
            'status': 'success',
            'canceled_orders': cancelled_ids
        }

    def orderbook(self) -> Dict[str, Any]:
        """
        Simulate the order book by checking the status of orders submitted by the bot.
        This method is used by GridTradingBot.
        """
        logger.info("Mock Client: Bot is requesting order book.")
        orders_from_engine = self._adapter.get_orders()
        
        bot_orders = []
        
        # Add all active orders from engine
        for order in orders_from_engine:
            if order.id:
                status_map = {
                    OrderStatus.PENDING: 'open',
                    OrderStatus.SUBMITTED: 'open',
                    OrderStatus.FILLED: 'complete',
                    OrderStatus.CANCELLED: 'cancelled',
                    OrderStatus.REJECTED: 'rejected',
                }
                mapped_status = status_map.get(order.status, 'unknown')
                logger.debug(f"Mock Client: Order {order.id} - Status: {order.status} -> {mapped_status}, Price: {order.avg_fill_price or order.price}")
                
                bot_orders.append({
                    'orderid': order.id,
                    'order_status': mapped_status,
                    'price': order.avg_fill_price or order.price or 0.0
                })

        # Add recent fills that the bot hasn't processed yet
        if hasattr(self._adapter, 'recent_fills'):
            for order_id, fill_info in list(self._adapter.recent_fills.items()):
                fill_price = fill_info.get('filled_price') or fill_info.get('price', 0.0)
                logger.debug(f"Mock Client: Adding recent fill {order_id} - Status: complete, Price: {fill_price}")
                bot_orders.append({
                    'orderid': order_id,
                    'order_status': 'complete',
                    'price': fill_price
                })

        logger.info(f"Mock Client: Returning {len(bot_orders)} orders to bot")
        return {
            'status': 'success',
            'data': {'orders': bot_orders}
        }

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Simulate getting order status by checking with the backtesting engine.
        This method is used by SupertrendTradingBot.
        """
        orders_from_engine = self._adapter.get_orders()
        
        # Check active orders first
        for order in orders_from_engine:
            if order.id == order_id:
                status_map = {
                    OrderStatus.PENDING: 'OPEN',
                    OrderStatus.SUBMITTED: 'OPEN',
                    OrderStatus.FILLED: 'FILLED',
                    OrderStatus.CANCELLED: 'CANCELLED',
                    OrderStatus.REJECTED: 'REJECTED',
                }
                mapped_status = status_map.get(order.status, 'UNKNOWN')
                
                return {
                    'status': mapped_status,
                    'order_id': order.id,
                    'action': order.action.value.lower(),
                    'quantity': order.quantity,
                    'price': order.avg_fill_price or order.price or 0.0
                }

        # Check recent fills
        if hasattr(self._adapter, 'recent_fills') and order_id in self._adapter.recent_fills:
            fill_info = self._adapter.recent_fills[order_id]
            return {
                'status': 'FILLED',
                'order_id': order_id,
                'action': fill_info.get('action', 'buy'),
                'quantity': fill_info.get('quantity', 0),
                'price': fill_info['price']
            }

        # Order not found
        return {'status': 'UNKNOWN', 'order_id': order_id}

    def history(self, symbol: str, exchange: str, start_date: str, end_date: str, interval: str) -> pd.DataFrame:
        """
        Mock the history API call. For backtesting, we return the accumulated historical data
        that the adapter has been collecting from the on_bar calls.
        This method is used by SupertrendTradingBot.
        """
        if hasattr(self._adapter, 'historical_data') and self._adapter.historical_data is not None:
            logger.debug(f"Mock Client: Returning {len(self._adapter.historical_data)} historical bars to bot")
            return self._adapter.historical_data.copy()
        else:
            logger.warning("Mock Client: No historical data available, returning empty DataFrame")
            return pd.DataFrame()