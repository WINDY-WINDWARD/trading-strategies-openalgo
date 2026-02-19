from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Iterable

from ..core.errors import RepositoryError
from ..schemas.ohlcv_data import OHLCVCandle

logger = logging.getLogger(__name__)


class WarehouseRepository:
    """Data access layer for ticker and OHLCV data.

    This repository encapsulates all SQL operations against the underlying
    SQLite database, providing a higher-level interface for managing ticker
    identifiers and persisting/retrieving OHLCV candle data. It abstracts
    insert, update, and query logic so that callers do not interact with raw
    SQL or database connections directly.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure_ticker(self, ticker: str) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO tickers (ticker) VALUES (?)",
                (ticker,),
            )
            _ = cursor
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"Ticker {ticker} could not be created")
            return int(row["id"])
        except sqlite3.Error as exc:
            logger.exception("Failed to ensure ticker %s", ticker)
            raise RepositoryError("Failed to ensure ticker") from exc

    def ticker_exists(self, ticker: str) -> bool:
        try:
            row = self.connection.execute(
                "SELECT 1 FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
            return row is not None
        except sqlite3.Error as exc:
            logger.exception("Failed to check ticker %s", ticker)
            raise RepositoryError("Failed to check ticker") from exc

    def list_tickers(self) -> list[str]:
        try:
            rows = self.connection.execute(
                "SELECT ticker FROM tickers ORDER BY ticker",
            ).fetchall()
            return [row["ticker"] for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Failed to list tickers")
            raise RepositoryError("Failed to list tickers") from exc

    def list_timeframes_for_ticker(self, ticker: str) -> list[str]:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to list timeframes for %s", ticker)
            raise RepositoryError("Failed to list timeframes") from exc
        if row is None:
            return []
        ticker_id = int(row["id"])
        try:
            rows = self.connection.execute(
                """
                SELECT DISTINCT timeframe
                FROM ohlcv
                WHERE ticker_id = ?
                ORDER BY timeframe
                """,
                (ticker_id,),
            ).fetchall()
            return [row["timeframe"] for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Failed to list timeframes for %s", ticker)
            raise RepositoryError("Failed to list timeframes") from exc

    def get_existing_epochs(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list[int]:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read epochs for %s", ticker)
            raise RepositoryError("Failed to read epochs") from exc
        if row is None:
            return []

        ticker_id = int(row["id"])
        try:
            rows = self.connection.execute(
                """
                SELECT epoch FROM ohlcv
                WHERE ticker_id = ? AND timeframe = ? AND epoch BETWEEN ? AND ?
                ORDER BY epoch
                """,
                (ticker_id, timeframe, start_epoch, end_epoch),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to read epochs for %s", ticker)
            raise RepositoryError("Failed to read epochs") from exc
        return [int(item["epoch"]) for item in rows]

    def upsert_ohlcv_batch(
        self,
        ticker: str,
        timeframe: str,
        candles: Iterable[OHLCVCandle],
        use_transaction: bool = True,
    ) -> int:
        ticker_id = self.ensure_ticker(ticker)
        candle_list = list(candles)
        if not candle_list:
            return 0

        def _execute() -> None:
            self.connection.executemany(
                """
                INSERT INTO ohlcv (
                    ticker_id, timeframe, epoch, open, high, low, close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker_id, timeframe, epoch) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
                """,
                [
                    (
                        ticker_id,
                        timeframe,
                        candle.epoch,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                    )
                    for candle in candle_list
                ],
            )

            self.connection.execute(
                """
                INSERT INTO ticker_timeframes (
                    ticker_id,
                    timeframe,
                    last_updated_epoch,
                    current_range_start_epoch,
                    current_range_end_epoch
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ticker_id, timeframe) DO UPDATE SET
                    last_updated_epoch = excluded.last_updated_epoch,
                    current_range_start_epoch = MIN(ticker_timeframes.current_range_start_epoch, excluded.current_range_start_epoch),
                    current_range_end_epoch = MAX(ticker_timeframes.current_range_end_epoch, excluded.current_range_end_epoch)
                """,
                (
                    ticker_id,
                    timeframe,
                    max(candle.epoch for candle in candle_list),
                    min(candle.epoch for candle in candle_list),
                    max(candle.epoch for candle in candle_list),
                ),
            )

        try:
            if use_transaction:
                with self.connection:
                    _execute()
            else:
                _execute()
        except sqlite3.Error as exc:
            logger.exception("Failed to upsert candles for %s %s", ticker, timeframe)
            raise RepositoryError("Failed to upsert candles") from exc

        return len(candle_list)

    def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list[dict]:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read candles for %s", ticker)
            raise RepositoryError("Failed to read candles") from exc
        if row is None:
            return []
        ticker_id = int(row["id"])
        try:
            rows = self.connection.execute(
                """
                SELECT epoch, open, high, low, close, volume
                FROM ohlcv
                WHERE ticker_id = ? AND timeframe = ? AND epoch BETWEEN ? AND ?
                ORDER BY epoch
                """,
                (ticker_id, timeframe, start_epoch, end_epoch),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to read candles for %s", ticker)
            raise RepositoryError("Failed to read candles") from exc

        return [
            {
                "epoch": int(item["epoch"]),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": int(item["volume"]),
            }
            for item in rows
        ]

    def get_ohlcv_page(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
        limit: int,
        offset: int,
    ) -> list[dict]:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read candles for %s", ticker)
            raise RepositoryError("Failed to read candles") from exc
        if row is None:
            return []
        ticker_id = int(row["id"])
        try:
            rows = self.connection.execute(
                """
                SELECT epoch, open, high, low, close, volume
                FROM ohlcv
                WHERE ticker_id = ? AND timeframe = ? AND epoch BETWEEN ? AND ?
                ORDER BY epoch DESC
                LIMIT ? OFFSET ?
                """,
                (ticker_id, timeframe, start_epoch, end_epoch, limit, offset),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to read candles for %s", ticker)
            raise RepositoryError("Failed to read candles") from exc

        return [
            {
                "epoch": int(item["epoch"]),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": int(item["volume"]),
            }
            for item in rows
        ]

    def get_ohlcv_count(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> int:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to count candles for %s", ticker)
            raise RepositoryError("Failed to count candles") from exc
        if row is None:
            return 0
        ticker_id = int(row["id"])
        try:
            data = self.connection.execute(
                """
                SELECT COUNT(1) AS total
                FROM ohlcv
                WHERE ticker_id = ? AND timeframe = ? AND epoch BETWEEN ? AND ?
                """,
                (ticker_id, timeframe, start_epoch, end_epoch),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to count candles for %s", ticker)
            raise RepositoryError("Failed to count candles") from exc
        if data is None:
            return 0
        return int(data["total"])

    def get_ticker_timeframe_meta(self, ticker: str, timeframe: str) -> dict | None:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read metadata for %s", ticker)
            raise RepositoryError("Failed to read metadata") from exc
        if row is None:
            return None
        ticker_id = int(row["id"])
        try:
            data = self.connection.execute(
                """
                SELECT last_updated_epoch, current_range_start_epoch, current_range_end_epoch
                FROM ticker_timeframes
                WHERE ticker_id = ? AND timeframe = ?
                """,
                (ticker_id, timeframe),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read metadata for %s", ticker)
            raise RepositoryError("Failed to read metadata") from exc
        if data is None:
            return None
        return {
            "last_updated_epoch": data["last_updated_epoch"],
            "current_range_start_epoch": data["current_range_start_epoch"],
            "current_range_end_epoch": data["current_range_end_epoch"],
        }

    def create_job(self, job_id: str, job_type: str, status: str) -> None:
        try:
            now = int(time.time())
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO jobs (job_id, job_type, status, created_at, updated_at, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, job_type, status, now, now, json.dumps({})),
                )
        except sqlite3.Error as exc:
            logger.exception("Failed to create job %s", job_id)
            raise RepositoryError("Failed to create job") from exc

    def update_job(self, job_id: str, status: str, data: dict) -> None:
        try:
            now = int(time.time())
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, updated_at = ?, data = ?
                    WHERE job_id = ?
                    """,
                    (status, now, json.dumps(data), job_id),
                )
        except sqlite3.Error as exc:
            logger.exception("Failed to update job %s", job_id)
            raise RepositoryError("Failed to update job") from exc

    def get_job(self, job_id: str) -> dict | None:
        try:
            row = self.connection.execute(
                "SELECT job_id, job_type, status, created_at, updated_at, data FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to read job %s", job_id)
            raise RepositoryError("Failed to read job") from exc
        if row is None:
            return None
        payload = json.loads(row["data"]) if row["data"] else {}
        payload.update(
            {
                "job_id": row["job_id"],
                "job_type": row["job_type"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        clauses = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = ""
        if limit is not None:
            limit_clause = "LIMIT ? OFFSET ?"
            params.extend([str(limit), str(offset or 0)])
        try:
            rows = self.connection.execute(
                f"""
                SELECT job_id, job_type, status, created_at, updated_at, data
                FROM jobs
                {where_clause}
                ORDER BY created_at DESC
                {limit_clause}
                """,
                tuple(params),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to list jobs")
            raise RepositoryError("Failed to list jobs") from exc
        jobs = []
        for row in rows:
            payload = json.loads(row["data"]) if row["data"] else {}
            payload.update(
                {
                    "job_id": row["job_id"],
                    "job_type": row["job_type"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
            jobs.append(payload)
        return jobs

    def count_jobs(self, status: str | None = None, job_type: str | None = None) -> int:
        clauses = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            row = self.connection.execute(
                f"SELECT COUNT(1) AS total FROM jobs {where_clause}",
                tuple(params),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to count jobs")
            raise RepositoryError("Failed to count jobs") from exc
        if row is None:
            return 0
        return int(row["total"])

    def delete_ohlcv(
        self,
        ticker: str,
        timeframe: str | None,
        start_epoch: int | None,
        end_epoch: int | None,
    ) -> int:
        try:
            row = self.connection.execute(
                "SELECT id FROM tickers WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to delete candles for %s", ticker)
            raise RepositoryError("Failed to delete candles") from exc
        if row is None:
            return 0
        ticker_id = int(row["id"])

        if timeframe is None and start_epoch is None and end_epoch is None:
            try:
                with self.connection:
                    deleted = self.connection.execute(
                        "DELETE FROM tickers WHERE id = ?",
                        (ticker_id,),
                    )
                return int(deleted.rowcount)
            except sqlite3.Error as exc:
                logger.exception("Failed to delete ticker %s", ticker)
                raise RepositoryError("Failed to delete ticker") from exc

        clauses = ["ticker_id = ?"]
        params: list[int | str] = [ticker_id]
        if timeframe is not None:
            clauses.append("timeframe = ?")
            params.append(timeframe)
        if start_epoch is not None and end_epoch is not None:
            clauses.append("epoch BETWEEN ? AND ?")
            params.extend([start_epoch, end_epoch])

        try:
            with self.connection:
                deleted = self.connection.execute(
                    f"DELETE FROM ohlcv WHERE {' AND '.join(clauses)}",
                    tuple(params),
                )

            return int(deleted.rowcount)
        except sqlite3.Error as exc:
            logger.exception("Failed to delete ohlcv for %s", ticker)
            raise RepositoryError("Failed to delete candles") from exc

    def get_last_epoch(self, ticker: str, timeframe: str) -> int | None:
        row = self.connection.execute(
            "SELECT id FROM tickers WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        ticker_id = int(row["id"])

        data = self.connection.execute(
            "SELECT MAX(epoch) AS max_epoch FROM ohlcv WHERE ticker_id = ? AND timeframe = ?",
            (ticker_id, timeframe),
        ).fetchone()
        if data is None or data["max_epoch"] is None:
            return None
        return int(data["max_epoch"])
