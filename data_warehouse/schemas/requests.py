from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]


class EpochRange(BaseModel):
    start_epoch: int = Field(..., ge=0)
    end_epoch: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "EpochRange":
        if self.end_epoch < self.start_epoch:
            raise ValueError("end_epoch must be greater than or equal to start_epoch")
        return self


class AddStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe = "1d"
    range: EpochRange | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class DeleteStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe | None = None
    range: EpochRange | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class UpdateStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe = "1d"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class GetStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe = "1d"
    range: EpochRange | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class BulkAddRow(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe = "1d"
    range: EpochRange | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class BulkAddRequest(BaseModel):
    rows: list[BulkAddRow] = Field(default_factory=list, min_length=1)
