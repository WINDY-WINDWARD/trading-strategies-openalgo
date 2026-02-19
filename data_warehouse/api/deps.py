from __future__ import annotations

from pathlib import Path
import os

from typing import Protocol, cast

from ..core.openalgo_client import OpenAlgoClient
from ..db.db import get_connection, init_db
from ..db.repository import WarehouseRepository
from ..services.warehouse_service import JobStore, WarehouseService
from ..schemas.ohlcv_data import OHLCVCandle


_service: WarehouseService | None = None
_service_db_path: str | None = None


class _OpenAlgoProvider(Protocol):
    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list[OHLCVCandle]: ...


class _FakeOpenAlgoClient:
    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list:
        _ = ticker
        _ = timeframe
        if start_epoch > end_epoch:
            return []
        return [
            OHLCVCandle(
                epoch=start_epoch,
                open=100.0,
                high=110.0,
                low=90.0,
                close=105.0,
                volume=1000,
            )
        ]


def get_service() -> WarehouseService:
    global _service, _service_db_path
    env_db_path = os.getenv("DW_DB_PATH")
    db_path = env_db_path or str(
        Path(__file__).resolve().parents[1] / "db" / "tickerData.db"
    )
    if _service is None or _service_db_path != db_path:
        if _service is not None:
            try:
                _service.repository.connection.close()
            except Exception:
                pass
        init_db(db_path)
        connection = get_connection(db_path)
        repository = WarehouseRepository(connection)
        if os.getenv("DW_TESTING") == "1":
            provider: _OpenAlgoProvider = _FakeOpenAlgoClient()
        else:
            provider = OpenAlgoClient()
        _service = WarehouseService(
            repository=repository,
            provider=cast(_OpenAlgoProvider, provider),
            job_store=JobStore(repository),
        )
        _service_db_path = db_path
    return _service
