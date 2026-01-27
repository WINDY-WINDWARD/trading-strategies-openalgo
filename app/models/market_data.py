# app/models/market_data.py
"""
Market data models.
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Candle(BaseModel):
    """OHLCV candle data."""
    timestamp: datetime = Field(..., description="Candle timestamp")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume")
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")

    @property
    def typical_price(self) -> float:
        """Calculate typical price (HLC/3)."""
        return (self.high + self.low + self.close) / 3

    @property
    def ohlc4(self) -> float:
        """Calculate OHLC4 average."""
        return (self.open + self.high + self.low + self.close) / 4

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'symbol': self.symbol,
            'exchange': self.exchange
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Quote(BaseModel):
    """Real-time quote data."""
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    timestamp: datetime = Field(..., description="Quote timestamp")
    bid: Optional[float] = Field(None, description="Bid price")
    ask: Optional[float] = Field(None, description="Ask price")
    last: float = Field(..., description="Last traded price")
    volume: Optional[float] = Field(None, description="Volume")
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.last

    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'timestamp': self.timestamp.isoformat(),
            'bid': self.bid,
            'ask': self.ask,
            'last': self.last,
            'volume': self.volume
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
