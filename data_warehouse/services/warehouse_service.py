from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
from typing import Callable
import json

from ..core.gap_detection import TIMEFRAME_TO_SECONDS, detect_missing_ranges
from typing import Protocol

from ..core.openalgo_client import OpenAlgoClient
from ..db.repository import WarehouseRepository
from ..core.errors import ProviderError, RepositoryError
from ..schemas.ohlcv_data import OHLCVCandle
from ..schemas.requests import (
    AddStockRequest,
    BulkAddRequest,
    DeleteStockRequest,
    EpochRange,
    GapFillRequest,
    GetStockRequest,
    Timeframe,
    UpdateAllRequest,
    UpdateStockRequest,
)
from typing import cast


class JobStore:
    """Persistent store for tracking asynchronous job state and lifecycle."""

    def __init__(self, repository: WarehouseRepository):
        self.repository = repository

    def create(self, job_type: str) -> dict:
        job_id = str(uuid.uuid4())
        try:
            self.repository.create_job(job_id, job_type, "queued")
            stored = self.repository.get_job(job_id)
            if stored:
                return stored
        except Exception:
            pass
        return {"job_id": job_id, "job_type": job_type, "status": "queued"}

    def update(self, job_id: str, **kwargs) -> dict:
        status = kwargs.pop("status", None)
        try:
            payload = self.repository.get_job(job_id) or {}
        except Exception:
            payload = {}
        payload.update(kwargs)
        if status is None:
            status = payload.get("status", "queued")
        try:
            self.repository.update_job(job_id, status, payload)
            stored = self.repository.get_job(job_id)
            if stored:
                return stored
        except Exception:
            pass
        payload["status"] = status
        return payload

    def get(self, job_id: str) -> dict | None:
        try:
            return self.repository.get_job(job_id)
        except Exception:
            return None

    def list(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        try:
            return self.repository.list_jobs(
                status=status, job_type=job_type, limit=limit, offset=offset
            )
        except Exception:
            return []


class WarehouseService:
    def __init__(
        self,
        repository: WarehouseRepository,
        provider: OpenAlgoProvider,
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

    def enqueue_update_all(self, request: UpdateAllRequest) -> dict:
        return self.job_store.create("update_all")

    def enqueue_bulk_add(self, request: BulkAddRequest) -> dict:
        return self.job_store.create("bulk_add")

    def enqueue_delete(self, request: DeleteStockRequest) -> dict:
        return self.job_store.create("delete")

    def enqueue_gap_fill(self, request: GapFillRequest) -> dict:
        return self.job_store.create("gap_fill")

    def process_add(self, job_id: str, request: AddStockRequest) -> None:
        selected_range: EpochRange = self.default_range()
        try:
            self.job_store.update(job_id, status="running")
            self.repository.ensure_ticker(request.ticker)
            if request.range is not None:
                selected_range = request.range
            if request.start_date and request.end_date:
                start_epoch = int(
                    datetime.combine(
                        request.start_date, datetime.min.time()
                    ).timestamp()
                )
                end_epoch = int(
                    datetime.combine(request.end_date, datetime.max.time()).timestamp()
                )
                selected_range = EpochRange(
                    start_epoch=start_epoch, end_epoch=end_epoch
                )

            self.job_store.update(
                job_id,
                selected_range=selected_range.model_dump(),
                current_ticker=request.ticker,
                current_timeframe=request.timeframe,
            )

            has_existing_data = (
                self.repository.get_last_epoch(request.ticker, request.timeframe)
                is not None
            )

            if not has_existing_data:
                try:
                    candles = self.provider.fetch_ohlcv(
                        ticker=request.ticker,
                        timeframe=request.timeframe,
                        start_epoch=selected_range.start_epoch,
                        end_epoch=selected_range.end_epoch,
                    )
                except Exception as exc:
                    logger.exception("Provider fetch failed")
                    raise ProviderError("Provider fetch failed") from exc

                self.job_store.update(
                    job_id,
                    fetched_count=len(candles),
                    message="initial fetch",
                )

                inserted = self.repository.upsert_ohlcv_batch(
                    ticker=request.ticker,
                    timeframe=request.timeframe,
                    candles=candles,
                )
                if inserted == 0:
                    self.job_store.update(
                        job_id,
                        status="failed",
                        error="no candles returned for requested range",
                    )
                    return

                self.job_store.update(
                    job_id,
                    status="completed",
                    inserted=inserted,
                    gaps_filled=0,
                    message="full range inserted",
                )
                return

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

            if request.timeframe in {"1d", "1w", "1M"} and len(gaps) > 1:
                gaps = [(selected_range.start_epoch, selected_range.end_epoch)]
            elif gaps:
                gaps = self._chunk_gaps(gaps, request.timeframe)

            self.job_store.update(
                job_id,
                gap_count=len(gaps),
                message="gap scan complete" if gaps else "no gaps found",
            )

            inserted = 0
            if gaps:
                for gap_start, gap_end in gaps:
                    try:
                        candles = self.provider.fetch_ohlcv(
                            ticker=request.ticker,
                            timeframe=request.timeframe,
                            start_epoch=gap_start,
                            end_epoch=gap_end,
                        )
                    except Exception as exc:
                        logger.exception("Provider fetch failed")
                        raise ProviderError("Provider fetch failed") from exc
                    self.job_store.update(
                        job_id,
                        current_gap={
                            "start_epoch": gap_start,
                            "end_epoch": gap_end,
                        },
                        fetched_count=len(candles),
                    )
                    inserted += self.repository.upsert_ohlcv_batch(
                        ticker=request.ticker,
                        timeframe=request.timeframe,
                        candles=candles,
                    )
                if inserted == 0:
                    self.job_store.update(
                        job_id,
                        status="failed",
                        error="no candles returned for requested gaps",
                    )
                    return
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
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Add job failed")
            self.repository.create_failed_ingestion(
                ticker=request.ticker,
                timeframe=request.timeframe,
                error_reason=str(exc),
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
            )
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("Add job failed")
            self.repository.create_failed_ingestion(
                ticker=request.ticker,
                timeframe=request.timeframe,
                error_reason="unexpected error",
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
            )
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def _chunk_gaps(
        self, gaps: list[tuple[int, int]], timeframe: str
    ) -> list[tuple[int, int]]:
        if not gaps:
            return []
        chunk_days = {
            "1m": 30,
            "5m": 30,
            "15m": 30,
            "1h": 120,
            "4h": 120,
        }.get(timeframe)
        if not chunk_days:
            return gaps
        max_span = chunk_days * 24 * 60 * 60
        chunked: list[tuple[int, int]] = []
        for start, end in gaps:
            current = start
            while current <= end:
                chunk_end = min(current + max_span - 1, end)
                chunked.append((current, chunk_end))
                current = chunk_end + 1
        return chunked

    def _intersect_ranges(
        self,
        primary: list[tuple[int, int]],
        secondary: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        intersections: list[tuple[int, int]] = []
        i = 0
        j = 0
        while i < len(primary) and j < len(secondary):
            start_a, end_a = primary[i]
            start_b, end_b = secondary[j]
            start = max(start_a, start_b)
            end = min(end_a, end_b)
            if start <= end:
                intersections.append((start, end))
            if end_a < end_b:
                i += 1
            else:
                j += 1
        return intersections

    def _subtract_ranges(
        self,
        source: list[tuple[int, int]],
        exclusions: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if not source or not exclusions:
            return source
        remaining: list[tuple[int, int]] = []
        exclusion_index = 0
        for start, end in source:
            current_start = start
            while (
                exclusion_index < len(exclusions)
                and exclusions[exclusion_index][1] < current_start
            ):
                exclusion_index += 1
            scan_index = exclusion_index
            while scan_index < len(exclusions) and exclusions[scan_index][0] <= end:
                exclude_start, exclude_end = exclusions[scan_index]
                if exclude_start > current_start:
                    remaining.append((current_start, min(end, exclude_start - 1)))
                if exclude_end >= end:
                    current_start = end + 1
                    break
                current_start = exclude_end + 1
                scan_index += 1
            if current_start <= end:
                remaining.append((current_start, end))
        return remaining

    def process_update(self, job_id: str, request: UpdateStockRequest) -> None:
        try:
            self.job_store.update(job_id, status="running")
            self.repository.ensure_ticker(request.ticker)
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
            try:
                candles = self.provider.fetch_ohlcv(
                    ticker=request.ticker,
                    timeframe=request.timeframe,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                )
            except Exception as exc:
                logger.exception("Provider fetch failed")
                raise ProviderError("Provider fetch failed") from exc
            inserted = self.repository.upsert_ohlcv_batch(
                ticker=request.ticker,
                timeframe=request.timeframe,
                candles=candles,
            )
            self.job_store.update(job_id, status="completed", inserted=inserted)
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Update job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("Update job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def process_update_all(self, job_id: str, request: UpdateAllRequest) -> None:
        try:
            tickers = self.repository.list_tickers()
            total = len(tickers)
            self.job_store.update(
                job_id,
                status="running",
                total_count=total,
                processed_count=0,
                progress_pct=0,
                current_timeframe=request.timeframe,
            )

            for index, ticker in enumerate(tickers, start=1):
                self.job_store.update(
                    job_id,
                    current_ticker=ticker,
                    current_timeframe=request.timeframe,
                    processed_count=index - 1,
                    progress_pct=min(100, int(round(((index - 1) / total) * 100)))
                    if total
                    else 0,
                )
                update_request = UpdateStockRequest(
                    ticker=ticker, timeframe=request.timeframe
                )
                update_job = self.job_store.create("update")
                self.process_update(update_job["job_id"], update_request)
                time.sleep(0.2)

            self.job_store.update(
                job_id,
                status="completed",
                processed_count=total,
                progress_pct=100,
            )
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Update all job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception:
            logger.exception("Update all job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def process_bulk_add(self, job_id: str, request: BulkAddRequest) -> None:
        try:
            total = len(request.rows)
            self.job_store.update(
                job_id,
                status="running",
                total_count=total,
                processed_count=0,
                progress_pct=0,
            )
            successes = 0
            failures: list[dict] = []

            for index, row in enumerate(request.rows, start=1):
                progress_pct = (
                    min(100, int(round(((index - 1) / total) * 100))) if total else 0
                )
                self.job_store.update(
                    job_id,
                    current_ticker=row.ticker,
                    current_timeframe=row.timeframe,
                    total_count=total,
                    processed_count=index - 1,
                    progress_pct=progress_pct,
                )
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
                    failures.append({"row": index - 1, "error": str(exc)})
                progress_pct = (
                    min(100, int(round((index / total) * 100))) if total else 100
                )
                self.job_store.update(
                    job_id,
                    current_ticker=row.ticker,
                    current_timeframe=row.timeframe,
                    total_count=total,
                    processed_count=index,
                    progress_pct=progress_pct,
                )

            self.job_store.update(
                job_id,
                status="completed",
                success_count=successes,
                failure_count=len(failures),
                failures=failures,
            )
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Bulk add job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("Bulk add job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def process_bulk_csv(self, job_id: str, rows: list[dict]) -> None:
        try:
            self.job_store.update(job_id, status="running")
            failures: list[dict] = []
            requests: list[AddStockRequest] = []

            for index, row in enumerate(rows):
                try:
                    for key in ("range", "start_date", "end_date"):
                        if (
                            key in row
                            and isinstance(row[key], str)
                            and not row[key].strip()
                        ):
                            row[key] = None
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

            total = len(requests)
            self.job_store.update(
                job_id,
                status="running",
                total_count=total,
                processed_count=0,
                progress_pct=0,
            )
            with self.repository.connection:
                for index, add_request in enumerate(requests, start=1):
                    progress_pct = (
                        min(100, int(round(((index - 1) / total) * 100)))
                        if total
                        else 0
                    )
                    self.job_store.update(
                        job_id,
                        current_ticker=add_request.ticker,
                        current_timeframe=add_request.timeframe,
                        total_count=total,
                        processed_count=index - 1,
                        progress_pct=progress_pct,
                    )
                    selected_range = add_request.range
                    if add_request.start_date and add_request.end_date:
                        start_epoch = int(
                            datetime.combine(
                                add_request.start_date, datetime.min.time()
                            ).timestamp()
                        )
                        end_epoch = int(
                            datetime.combine(
                                add_request.end_date, datetime.max.time()
                            ).timestamp()
                        )
                        selected_range = EpochRange(
                            start_epoch=start_epoch, end_epoch=end_epoch
                        )
                    if selected_range is None:
                        selected_range = self.default_range()

                    has_existing_data = (
                        self.repository.get_last_epoch(
                            add_request.ticker, add_request.timeframe
                        )
                        is not None
                    )
                    if not has_existing_data:
                        candles = self.provider.fetch_ohlcv(
                            ticker=add_request.ticker,
                            timeframe=add_request.timeframe,
                            start_epoch=selected_range.start_epoch,
                            end_epoch=selected_range.end_epoch,
                        )
                        self.repository.upsert_ohlcv_batch(
                            ticker=add_request.ticker,
                            timeframe=add_request.timeframe,
                            candles=candles,
                            use_transaction=False,
                        )
                        progress_pct = (
                            min(100, int(round((index / total) * 100)))
                            if total
                            else 100
                        )
                        self.job_store.update(
                            job_id,
                            current_ticker=add_request.ticker,
                            current_timeframe=add_request.timeframe,
                            total_count=total,
                            processed_count=index,
                            progress_pct=progress_pct,
                        )
                        continue

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
                    progress_pct = (
                        min(100, int(round((index / total) * 100))) if total else 100
                    )
                    self.job_store.update(
                        job_id,
                        current_ticker=add_request.ticker,
                        current_timeframe=add_request.timeframe,
                        total_count=total,
                        processed_count=index,
                        progress_pct=progress_pct,
                    )

            self.job_store.update(
                job_id,
                status="completed",
                success_count=len(requests),
                failure_count=0,
                failures=[],
            )
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Bulk CSV job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("Bulk CSV job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def process_gap_fill(self, job_id: str, request: GapFillRequest) -> None:
        try:
            tickers = self.repository.list_tickers()
            selected_range = request.range
            if request.start_date and request.end_date:
                start_epoch = int(
                    datetime.combine(
                        request.start_date, datetime.min.time()
                    ).timestamp()
                )
                end_epoch = int(
                    datetime.combine(request.end_date, datetime.max.time()).timestamp()
                )
                selected_range = EpochRange(
                    start_epoch=start_epoch, end_epoch=end_epoch
                )
            if selected_range is None:
                selected_range = self.default_range()

            total = len(tickers)
            self.job_store.update(
                job_id,
                status="running",
                total_count=total,
                processed_count=0,
                progress_pct=0,
                selected_range=selected_range.model_dump(),
                current_timeframe=request.timeframe,
            )

            interval_seconds = TIMEFRAME_TO_SECONDS[request.timeframe]
            gap_cache: dict[str, list[tuple[int, int]]] = {}
            common_gaps: list[tuple[int, int]] | None = None

            for ticker in tickers:
                try:
                    existing_epochs = self.repository.get_existing_epochs(
                        ticker=ticker,
                        timeframe=request.timeframe,
                        start_epoch=selected_range.start_epoch,
                        end_epoch=selected_range.end_epoch,
                    )
                except RepositoryError:
                    existing_epochs = []

                gaps = detect_missing_ranges(
                    start_epoch=selected_range.start_epoch,
                    end_epoch=selected_range.end_epoch,
                    existing_epochs=existing_epochs,
                    interval_seconds=interval_seconds,
                )
                gap_cache[ticker] = gaps
                if common_gaps is None:
                    common_gaps = list(gaps)
                else:
                    common_gaps = self._intersect_ranges(common_gaps, gaps)

            common_gaps = common_gaps or []
            self.job_store.update(
                job_id,
                common_gap_count=len(common_gaps),
                message="common gaps excluded" if common_gaps else "no common gaps",
            )

            for index, ticker in enumerate(tickers, start=1):
                self.job_store.update(
                    job_id,
                    current_ticker=ticker,
                    current_timeframe=request.timeframe,
                    processed_count=index - 1,
                    progress_pct=min(100, int(round(((index - 1) / total) * 100)))
                    if total
                    else 0,
                )

                gaps = gap_cache.get(ticker, [])
                excluded = (
                    self._intersect_ranges(gaps, common_gaps) if common_gaps else []
                )
                specific_gaps = (
                    self._subtract_ranges(gaps, common_gaps) if common_gaps else gaps
                )
                if specific_gaps:
                    specific_gaps = self._chunk_gaps(specific_gaps, request.timeframe)

                self.job_store.update(
                    job_id,
                    gap_count=len(specific_gaps),
                    excluded_common_gap_count=len(excluded),
                    message="gap scan complete" if specific_gaps else "no gaps found",
                )

                if specific_gaps:
                    for gap_start, gap_end in specific_gaps:
                        try:
                            candles = self.provider.fetch_ohlcv(
                                ticker=ticker,
                                timeframe=request.timeframe,
                                start_epoch=gap_start,
                                end_epoch=gap_end,
                            )
                        except Exception as exc:
                            logger.exception("Provider fetch failed")
                            raise ProviderError("Provider fetch failed") from exc
                        self.job_store.update(
                            job_id,
                            current_gap={
                                "start_epoch": gap_start,
                                "end_epoch": gap_end,
                            },
                            fetched_count=len(candles),
                        )
                        if candles:
                            self.repository.upsert_ohlcv_batch(
                                ticker=ticker,
                                timeframe=request.timeframe,
                                candles=candles,
                            )
                        time.sleep(0.4)
                time.sleep(0.2)

            self.job_store.update(
                job_id,
                status="completed",
                processed_count=total,
                progress_pct=100,
            )
        except (RepositoryError, ProviderError) as exc:
            logger.exception("Gap fill job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception:
            logger.exception("Gap fill job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

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
        self._hydrate_missing_data(
            ticker=request.ticker,
            timeframe=request.timeframe,
            selected_range=selected_range,
        )
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

    def get_ohlcv_range(
        self,
        ticker: str,
        timeframe: str,
        selected_range: EpochRange,
    ) -> list[dict]:
        self._hydrate_missing_data(
            ticker=ticker,
            timeframe=timeframe,
            selected_range=selected_range,
        )
        return self.repository.get_ohlcv(
            ticker=ticker,
            timeframe=timeframe,
            start_epoch=selected_range.start_epoch,
            end_epoch=selected_range.end_epoch,
        )

    def _hydrate_missing_data(
        self,
        ticker: str,
        timeframe: str,
        selected_range: EpochRange,
    ) -> None:
        try:
            current_count = self.repository.get_ohlcv_count(
                ticker=ticker,
                timeframe=timeframe,
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
            )
        except RepositoryError as exc:
            logger.exception("Ticker lookup failed")
            raise RepositoryError("Ticker lookup failed") from exc

        if current_count > 0:
            return

        try:
            candles = self.provider.fetch_ohlcv(
                ticker=ticker,
                timeframe=timeframe,
                start_epoch=selected_range.start_epoch,
                end_epoch=selected_range.end_epoch,
            )
        except Exception:
            logger.exception("Auto-fetch failed for %s %s", ticker, timeframe)
            return

        if not candles:
            return

        self.repository.upsert_ohlcv_batch(
            ticker=ticker,
            timeframe=timeframe,
            candles=candles,
        )

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
        except RepositoryError as exc:
            logger.exception("Delete job failed")
            self.job_store.update(job_id, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("Delete job failed")
            self.job_store.update(job_id, status="failed", error="unexpected error")

    def get_job(self, job_id: str) -> dict | None:
        return self.job_store.get(job_id)

    def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        return self.job_store.list(
            status=status,
            job_type=job_type,
            limit=limit,
            offset=offset,
        )

    def count_jobs(self, status: str | None = None, job_type: str | None = None) -> int:
        return self.repository.count_jobs(status, job_type)

    def list_tickers(self) -> list[str]:
        return self.repository.list_tickers()

    def list_timeframes_for_ticker(self, ticker: str) -> list[str]:
        return self.repository.list_timeframes_for_ticker(ticker)

    def list_tickers_with_timeframes(self) -> list[dict]:
        payload: list[dict] = []
        for ticker in self.repository.list_tickers():
            payload.append(
                {
                    "ticker": ticker,
                    "timeframes": self.repository.list_timeframes_for_ticker(ticker),
                }
            )
        return payload

    def list_ticker_metadata(self) -> list[dict]:
        return self.repository.list_ticker_metadata()

    def update_ticker_metadata(
        self,
        ticker: str,
        sector: str | None,
        company_name: str | None,
        exchange: str | None,
    ) -> None:
        self.repository.update_ticker_metadata(
            ticker=ticker,
            sector=sector,
            company_name=company_name,
            exchange=exchange,
        )

    def get_storage_stats(self) -> dict:
        return self.repository.get_storage_stats()

    def list_failed_ingestions(
        self,
        status: str = "failed",
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        return self.repository.list_failed_ingestions(
            status=status,
            limit=limit,
            offset=offset,
        )

    def count_failed_ingestions(self, status: str = "failed") -> int:
        return self.repository.count_failed_ingestions(status=status)

    def retry_failed_ingestion(
        self,
        failed_id: int,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> dict:
        """Retry a previously failed ingestion with new parameters."""
        job = self.job_store.create("retry_failed")
        self.repository.increment_failed_ingestion_retry(failed_id)

        try:
            request = AddStockRequest(
                ticker=ticker,
                timeframe=cast(Timeframe, timeframe),
                range=EpochRange(start_epoch=start_epoch, end_epoch=end_epoch),
            )
            self.process_add(job["job_id"], request)
            # Mark as resolved if successful
            self.repository.mark_failed_ingestion_resolved(failed_id)
        except Exception:
            pass  # process_add updates job status internally

        return self.job_store.get(job["job_id"]) or job


class OpenAlgoProvider(Protocol):
    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list[OHLCVCandle]: ...


logger = logging.getLogger(__name__)
