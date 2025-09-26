# app/core/events.py
"""
Event system for backtesting engine.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from ..models.orders import Order, OrderAction, OrderType
from ..models.market_data import Candle


class Event(ABC):
    """Base event class."""
    
    def __init__(self, timestamp: datetime):
        self.timestamp = timestamp
        self.type = self.__class__.__name__
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        pass


class MarketDataEvent(Event):
    """Market data event containing new candle data."""
    
    def __init__(self, candle: Candle):
        super().__init__(candle.timestamp)
        self.candle = candle
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'timestamp': self.timestamp.isoformat(),
            'candle': self.candle.to_dict()
        }


class OrderEvent(Event):
    """Order creation event."""
    
    def __init__(self, order: Order, timestamp: Optional[datetime] = None):
        super().__init__(timestamp or datetime.now())
        self.order = order
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'timestamp': self.timestamp.isoformat(),
            'order': self.order.to_dict()
        }


class FillEvent(Event):
    """Order fill event."""
    
    def __init__(
        self,
        order_id: str,
        fill_price: float,
        fill_quantity: float,
        commission: float = 0.0,
        timestamp: Optional[datetime] = None
    ):
        super().__init__(timestamp or datetime.now())
        self.order_id = order_id
        self.fill_price = fill_price
        self.fill_quantity = fill_quantity
        self.commission = commission
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'timestamp': self.timestamp.isoformat(),
            'order_id': self.order_id,
            'fill_price': self.fill_price,
            'fill_quantity': self.fill_quantity,
            'commission': self.commission
        }


class PositionEvent(Event):
    """Position update event."""
    
    def __init__(
        self,
        symbol: str,
        quantity: float,
        avg_price: float,
        unrealized_pnl: float,
        timestamp: Optional[datetime] = None
    ):
        super().__init__(timestamp or datetime.now())
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.unrealized_pnl = unrealized_pnl
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'unrealized_pnl': self.unrealized_pnl
        }


class PortfolioEvent(Event):
    """Portfolio update event."""
    
    def __init__(
        self,
        total_equity: float,
        cash: float,
        positions_value: float,
        unrealized_pnl: float,
        realized_pnl: float,
        timestamp: Optional[datetime] = None
    ):
        super().__init__(timestamp or datetime.now())
        self.total_equity = total_equity
        self.cash = cash
        self.positions_value = positions_value
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'timestamp': self.timestamp.isoformat(),
            'total_equity': self.total_equity,
            'cash': self.cash,
            'positions_value': self.positions_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl
        }


class EventQueue:
    """Event queue for managing backtest events."""
    
    def __init__(self):
        self.events = []
        self.event_handlers = {}
    
    def put(self, event: Event) -> None:
        """Add event to queue."""
        self.events.append(event)
    
    def get(self) -> Optional[Event]:
        """Get next event from queue."""
        try:
            return self.events.pop(0)
        except IndexError:
            return None
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return len(self.events) == 0
    
    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()
    
    def register_handler(self, event_type: str, handler) -> None:
        """Register event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def process_events(self) -> None:
        """Process all events in queue."""
        while not self.empty():
            event = self.get()
            if event and event.type in self.event_handlers:
                for handler in self.event_handlers[event.type]:
                    handler(event)
