from __future__ import annotations

from datetime import date
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
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_date_range(self) -> "AddStockRequest":
        if (self.start_date is None) ^ (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        return self


class DeleteStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe | None = None
    range: EpochRange | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timeframe", mode="before")
    @classmethod
    def normalize_timeframe(cls, value: str | None) -> str | None:
        if value in ("", None):
            return None
        return value


class UpdateStockRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    timeframe: Timeframe = "1d"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class UpdateTickerMetadataRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    sector: str | None = None
    company_name: str | None = None
    exchange: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("sector", "company_name", "exchange", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_date_range(self) -> "BulkAddRow":
        if (self.start_date is None) ^ (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        return self


class BulkAddRequest(BaseModel):
    rows: list[BulkAddRow] = Field(default_factory=list, min_length=1)


class GapFillRequest(BaseModel):
    timeframe: Timeframe = "1d"
    range: EpochRange | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "GapFillRequest":
        if (self.start_date is None) ^ (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        return self
