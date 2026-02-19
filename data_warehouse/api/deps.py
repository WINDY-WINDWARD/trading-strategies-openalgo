from __future__ import annotations

from pathlib import Path

from ..core.openalgo_client import OpenAlgoClient
from ..db.db import get_connection, init_db
from ..db.repository import WarehouseRepository
from ..services.warehouse_service import JobStore, WarehouseService


_service: WarehouseService | None = None


def get_service() -> WarehouseService:
    global _service
    if _service is None:
        db_path = Path(__file__).resolve().parents[1] / "db" / "tickerData.db"
        init_db(str(db_path))
        connection = get_connection(str(db_path))
        repository = WarehouseRepository(connection)
        provider = OpenAlgoClient()
        _service = WarehouseService(
            repository=repository,
            provider=provider,
            job_store=JobStore(),
        )
    return _service
