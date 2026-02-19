from pydantic import BaseModel, Field


class OHLCVCandle(BaseModel):
    epoch: int = Field(..., ge=0)
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(..., ge=0)
