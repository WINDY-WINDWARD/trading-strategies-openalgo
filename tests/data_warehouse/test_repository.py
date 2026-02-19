import sqlite3

import pytest

from data_warehouse.db.db import SCHEMA_SQL
from data_warehouse.db.repository import WarehouseRepository
from data_warehouse.schemas.ohlcv_data import OHLCVCandle


@pytest.fixture()
def repository() -> WarehouseRepository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    return WarehouseRepository(connection)


def test_upsert_overwrites_existing_candle(repository: WarehouseRepository) -> None:
    first = OHLCVCandle(
        epoch=1700000000,
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000,
    )
    repository.upsert_ohlcv_batch("RELIANCE", "1d", [first])

    replacement = OHLCVCandle(
        epoch=1700000000,
        open=200.0,
        high=210.0,
        low=190.0,
        close=205.0,
        volume=2000,
    )
    repository.upsert_ohlcv_batch("RELIANCE", "1d", [replacement])

    rows = repository.get_ohlcv("RELIANCE", "1d", 1700000000, 1700000000)
    assert rows == [
        {
            "epoch": 1700000000,
            "open": 200.0,
            "high": 210.0,
            "low": 190.0,
            "close": 205.0,
            "volume": 2000,
        }
    ]


def test_delete_range_respects_timeframe(repository: WarehouseRepository) -> None:
    candles = [
        OHLCVCandle(
            epoch=1700000000,
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=1000,
        ),
        OHLCVCandle(
            epoch=1700086400,
            open=120.0,
            high=130.0,
            low=115.0,
            close=125.0,
            volume=1200,
        ),
    ]
    repository.upsert_ohlcv_batch("RELIANCE", "1d", candles)
    repository.upsert_ohlcv_batch("RELIANCE", "1h", candles)

    deleted = repository.delete_ohlcv(
        ticker="RELIANCE",
        timeframe="1d",
        start_epoch=1700000000,
        end_epoch=1700086400,
    )

    assert deleted == 2
    remaining = repository.get_ohlcv("RELIANCE", "1h", 1700000000, 1700086400)
    assert len(remaining) == 2


def test_indexes_exist(repository: WarehouseRepository) -> None:
    rows = repository.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    index_names = {row["name"] for row in rows}

    assert "idx_ohlcv_ticker_timeframe_epoch" in index_names
    assert "idx_ticker_timeframes_ticker_timeframe" in index_names


def test_ticker_timeframes_updated_on_upsert(repository: WarehouseRepository) -> None:
    candles = [
        OHLCVCandle(
            epoch=1700000000,
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=1000,
        ),
        OHLCVCandle(
            epoch=1700086400,
            open=120.0,
            high=130.0,
            low=115.0,
            close=125.0,
            volume=1200,
        ),
    ]
    repository.upsert_ohlcv_batch("RELIANCE", "1d", candles)

    row = repository.connection.execute(
        """
        SELECT last_updated_epoch, current_range_start_epoch, current_range_end_epoch
        FROM ticker_timeframes
        """
    ).fetchone()

    assert row is not None
    assert int(row["last_updated_epoch"]) == 1700086400
    assert int(row["current_range_start_epoch"]) == 1700000000
    assert int(row["current_range_end_epoch"]) == 1700086400
