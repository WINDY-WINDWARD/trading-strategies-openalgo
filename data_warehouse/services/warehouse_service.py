from __future__ import annotations

import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
from typing import Callable
import json

from ..core.gap_detection import TIMEFRAME_TO_SECONDS, detect_missing_ranges
from ..core.openalgo_client import OpenAlgoClient
from ..db.repository import WarehouseRepository
from ..schemas.ohlcv_data import OHLCVCandle
from ..schemas.requests import (
    AddStockRequest,
    BulkAddRequest,
    DeleteStockRequest,
    EpochRange,
    GetStockRequest,
    UpdateStockRequest,
)



class JobStore:
    """In-memory store for tracking asynchronous job state and lifecycle.

    This class keeps job metadata (IDs, types, status, timestamps, etc.)
    in process-local memory and provides basic operations to create,
    update, retrieve, and list jobs. It is intended for lightweight
    job tracking and monitoring, and does not provide persistent storage.
    """
    def __init__(self):
        self._jobs: dict[str, dict] = {}

    def create(self, job_type: str) -> dict:
        job_id = str(uuid.uuid4())
        now = int(time.time())
        payload = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
        }
        self._jobs[job_id] = payload
        return payload

    def update(self, job_id: str, **kwargs) -> dict:
        job = self._jobs[job_id]
        job.update(kwargs)
        job["updated_at"] = int(time.time())
        return job

    def get(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def list(
        self, status: str | None = None, job_type: str | None = None
    ) -> list[dict]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.get("status") == status]
        if job_type:
            jobs = [job for job in jobs if job.get("job_type") == job_type]
        return sorted(jobs, key=lambda item: item.get("created_at", 0), reverse=True)


class WarehouseService:
    def __init__(
        self,
        repository: WarehouseRepository,
        provider: OpenAlgoClient,
        job_store: JobStore,
        clock: Callable[[], int] | None = None,
    ):
        self.repository = repository
        self.provider = provider
        self.job_store = job_store
        self.clock = clock or (lambda: int(time.time()))

    def default_range(self) -> EpochRange:
        end_epoch = self.clock()
        start_epoch = end_epoch - 365 * 24 * 60 * 60
        return EpochRange(start_epoch=start_epoch, end_epoch=end_epoch)

    def enqueue_add(self, request: AddStockRequest) -> dict:
        return self.job_store.create("add")

    def enqueue_update(self, request: UpdateStockRequest) -> dict:
        return self.job_store.create("update")

    def enqueue_bulk_add(self, request: BulkAddRequest) -> dict:
        return self.job_store.create("bulk_add")

    def enqueue_delete(self, request: DeleteStockRequest) -> dict:
        return self.job_store.create("delete")

    def process_add(self, job_id: str, request: AddStockRequest) -> None:
        try:
            self.job_store.update(job_id, status="running")
            selected_range = request.range or self.default_range()
            interval = TIMEFRAME_TO_SECONDS[request.timeframe]
            existing_epochs = self.repository.get_existing_epochs(
                ticker=request.ticker,
                timeframe=request.timeframe,
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
            )

            gaps = detect_missing_ranges(
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
                existing_epochs=existing_epochs,
                interval_seconds=interval,
            )

            inserted = 0
            if gaps:
                for gap_start, gap_end in gaps:
                    candles = self.provider.fetch_ohlcv(
                        ticker=request.ticker,
                        timeframe=request.timeframe,
                        start_epoch=gap_start,
                        end_epoch=gap_end,
                    )
                    inserted += self.repository.upsert_ohlcv_batch(
                        ticker=request.ticker,
                        timeframe=request.timeframe,
                        candles=candles,
                        use_transaction=False,
                    )
                self.job_store.update(
                    job_id,
                    status="completed",
                    inserted=inserted,
                    gaps_filled=len(gaps),
                )
                return

            self.job_store.update(
                job_id,
                status="completed",
                inserted=0,
                message="already present",
            )
        except Exception as exc:
            self.job_store.update(job_id, status="failed", error=str(exc))

    def process_update(self, job_id: str, request: UpdateStockRequest) -> None:
        try:
            self.job_store.update(job_id, status="running")
            last_epoch = self.repository.get_last_epoch(
                request.ticker, request.timeframe
            )
            if last_epoch is None:
                add_request = AddStockRequest(
                    ticker=request.ticker, timeframe=request.timeframe
                )
                self.process_add(job_id, add_request)
                return

            interval = TIMEFRAME_TO_SECONDS[request.timeframe]
            start_epoch = last_epoch + interval
            end_epoch = self.clock()
            candles = self.provider.fetch_ohlcv(
                ticker=request.ticker,
                timeframe=request.timeframe,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
            )
            inserted = self.repository.upsert_ohlcv_batch(
                ticker=request.ticker,
                timeframe=request.timeframe,
                candles=candles,
                use_transaction=False,
            )
            self.job_store.update(job_id, status="completed", inserted=inserted)
        except Exception as exc:
            self.job_store.update(job_id, status="failed", error=str(exc))

    def process_bulk_add(self, job_id: str, request: BulkAddRequest) -> None:
        try:
            self.job_store.update(job_id, status="running")
            successes = 0
            failures: list[dict] = []

            for index, row in enumerate(request.rows):
                try:
                    add_request = AddStockRequest(
                        ticker=row.ticker,
                        timeframe=row.timeframe,
                        range=row.range,
                    )
                    nested_job = self.job_store.create("bulk_item")
                    self.process_add(nested_job["job_id"], add_request)
                    successes += 1
                except Exception as exc:
                    failures.append({"row": index, "error": str(exc)})

            self.job_store.update(
                job_id,
                status="completed",
                success_count=successes,
                failure_count=len(failures),
                failures=failures,
            )
        except Exception as exc:
            self.job_store.update(job_id, status="failed", error=str(exc))

    def process_bulk_csv(self, job_id: str, rows: list[dict]) -> None:
        try:
            self.job_store.update(job_id, status="running")
            failures: list[dict] = []
            requests: list[AddStockRequest] = []

            for index, row in enumerate(rows):
                try:
                    if (
                        "range" in row
                        and isinstance(row["range"], str)
                        and row["range"].strip()
                    ):
                        row["range"] = json.loads(row["range"])
                    add_request = AddStockRequest.model_validate(row)
                    requests.append(add_request)
                except Exception as exc:
                    failures.append({"row": index, "error": str(exc)})

            if failures:
                raise ValueError("Bulk CSV contains invalid rows")

            with self.repository.connection:
                for add_request in requests:
                    selected_range = add_request.range or self.default_range()
                    interval = TIMEFRAME_TO_SECONDS[add_request.timeframe]
                    existing_epochs = self.repository.get_existing_epochs(
                        ticker=add_request.ticker,
                        timeframe=add_request.timeframe,
                        start_epoch=selected_range.start_epoch,
                        end_epoch=selected_range.end_epoch,
                    )

                    gaps = detect_missing_ranges(
                        start_epoch=selected_range.start_epoch,
                        end_epoch=selected_range.end_epoch,
                        existing_epochs=existing_epochs,
                        interval_seconds=interval,
                    )

                    if gaps:
                        for gap_start, gap_end in gaps:
                            candles = self.provider.fetch_ohlcv(
                                ticker=add_request.ticker,
                                timeframe=add_request.timeframe,
                                start_epoch=gap_start,
                                end_epoch=gap_end,
                            )
                            self.repository.upsert_ohlcv_batch(
                                ticker=add_request.ticker,
                                timeframe=add_request.timeframe,
                                candles=candles,
                                use_transaction=False,
                            )

            self.job_store.update(
                job_id,
                status="completed",
                success_count=len(requests),
                failure_count=0,
                failures=[],
            )
        except Exception as exc:
            self.job_store.update(job_id, status="failed", error=str(exc))

    def get_stock_data(self, request: GetStockRequest) -> dict:
        return self.get_stock_data_page(
            request=request,
            limit=1000,
            offset=0,
        )

    def get_stock_data_page(
        self,
        request: GetStockRequest,
        limit: int,
        offset: int,
    ) -> dict:
        selected_range = request.range or self.default_range()
        candles = self.repository.get_ohlcv_page(
            ticker=request.ticker,
            timeframe=request.timeframe,
            start_epoch=selected_range.start_epoch,
            end_epoch=selected_range.end_epoch,
            limit=limit,
            offset=offset,
        )
        total = self.repository.get_ohlcv_count(
            ticker=request.ticker,
            timeframe=request.timeframe,
            start_epoch=selected_range.start_epoch,
            end_epoch=selected_range.end_epoch,
        )
        meta = self.repository.get_ticker_timeframe_meta(
            ticker=request.ticker,
            timeframe=request.timeframe,
        )
        ist = ZoneInfo("Asia/Kolkata")
        for candle in candles:
            timestamp = datetime.fromtimestamp(
                candle["epoch"], tz=timezone.utc
            ).astimezone(ist)
            candle["timestamp_ist"] = timestamp.isoformat()
        return {
            "ticker": request.ticker,
            "timeframe": request.timeframe,
            "range": selected_range.model_dump(),
            "candles": candles,
            "total": total,
            "meta": meta,
            "limit": limit,
            "offset": offset,
        }

    def process_delete(self, job_id: str, request: DeleteStockRequest) -> None:
        try:
            self.job_store.update(job_id, status="running")
            start_epoch = request.range.start_epoch if request.range else None
            end_epoch = request.range.end_epoch if request.range else None
            deleted = self.repository.delete_ohlcv(
                ticker=request.ticker,
                timeframe=request.timeframe,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
            )
            self.job_store.update(job_id, status="completed", deleted=deleted)
        except Exception as exc:
            self.job_store.update(job_id, status="failed", error=str(exc))

    def get_job(self, job_id: str) -> dict | None:
        return self.job_store.get(job_id)

    def list_jobs(
        self, status: str | None = None, job_type: str | None = None
    ) -> list[dict]:
        return self.job_store.list(status, job_type)
