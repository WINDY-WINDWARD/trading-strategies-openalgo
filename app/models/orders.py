# app/models/orders.py
"""
Order and trade models.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class OrderAction(str, Enum):
    """Order action (side)."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Order(BaseModel):
    """Order model."""
    id: str = Field(..., description="Unique order ID")
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    action: OrderAction = Field(..., description="Order action (BUY/SELL)")
    order_type: OrderType = Field(..., description="Order type")
    quantity: float = Field(..., description="Order quantity")
    price: Optional[float] = Field(None, description="Order price (for limit orders)")
    stop_price: Optional[float] = Field(None, description="Stop price (for stop orders)")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Order status")
    
    # Execution details
    filled_quantity: float = Field(default=0.0, description="Filled quantity")
    avg_fill_price: Optional[float] = Field(None, description="Average fill price")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Order creation time")
    submitted_at: Optional[datetime] = Field(None, description="Order submission time")
    filled_at: Optional[datetime] = Field(None, description="Order fill time")
    cancelled_at: Optional[datetime] = Field(None, description="Order cancellation time")
    
    # Metadata
    strategy_id: Optional[str] = Field(None, description="Strategy identifier")
    notes: Optional[str] = Field(None, description="Order notes")

    @property
    def remaining_quantity(self) -> float:
        """Calculate remaining quantity."""
        return max(0, self.quantity - self.filled_quantity)

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        """Check if order is active (can be filled)."""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100

    def fill(self, quantity: float, price: float, timestamp: Optional[datetime] = None) -> None:
        """Fill the order partially or completely."""
        if timestamp is None:
            timestamp = datetime.now()
            
        # Update filled quantity
        self.filled_quantity = min(self.quantity, self.filled_quantity + quantity)
        
        # Update average fill price
        if self.avg_fill_price is None:
            self.avg_fill_price = price
        else:
            total_filled_value = (self.filled_quantity - quantity) * self.avg_fill_price + quantity * price
            self.avg_fill_price = total_filled_value / self.filled_quantity
        
        # Update status
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = timestamp
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED

    def cancel(self, timestamp: Optional[datetime] = None) -> None:
        """Cancel the order."""
        if timestamp is None:
            timestamp = datetime.now()
        self.status = OrderStatus.CANCELLED
        self.cancelled_at = timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'action': self.action.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'created_at': self.created_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'strategy_id': self.strategy_id,
            'notes': self.notes
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
