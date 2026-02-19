import pytest
from pydantic import ValidationError

from data_warehouse.schemas.requests import (
    AddStockRequest,
    BulkAddRequest,
    BulkAddRow,
    EpochRange,
)
from data_warehouse.schemas.ohlcv_data import OHLCVCandle


def test_add_stock_request_defaults_timeframe():
    request = AddStockRequest(ticker="RELIANCE")
    assert request.timeframe == "1d"


def test_add_stock_request_rejects_invalid_timeframe():
    with pytest.raises(ValidationError):
        AddStockRequest(ticker="RELIANCE", timeframe="2h")


def test_epoch_range_rejects_invalid_order():
    with pytest.raises(ValidationError):
        EpochRange(start_epoch=200, end_epoch=100)


def test_ohlcv_candle_requires_numeric_fields():
    with pytest.raises(ValidationError):
        OHLCVCandle(
            epoch=1700000000,
            open="x",
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )


def test_bulk_request_accepts_multiple_rows():
    payload = BulkAddRequest(
        rows=[
            BulkAddRow(ticker="RELIANCE", timeframe="1d", range=EpochRange(start_epoch=1, end_epoch=2)),
            BulkAddRow(ticker="TCS", timeframe="1h", range=EpochRange(start_epoch=10, end_epoch=20)),
        ]
    )
    assert len(payload.rows) == 2
