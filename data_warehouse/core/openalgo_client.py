from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import time

import pandas as pd

try:
    from openalgo import api as openalgo_api
except ImportError:  # pragma: no cover - handled at runtime
    openalgo_api = None

from ..schemas.ohlcv_data import OHLCVCandle


class OpenAlgoClient:
    """Thin fetch wrapper for OpenAlgo OHLCV data.

    This class is intentionally small so tests can inject fakes.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        exchange: str | None = None,
        min_request_interval: float = 0.1,
    ):
        self.api_key = api_key or os.getenv("OPENALGO_API_KEY")
        self.base_url = base_url or os.getenv(
            "OPENALGO_BASE_URL", "http://127.0.0.1:8800"
        )
        self.exchange = exchange or os.getenv("OPENALGO_EXCHANGE", "NSE")
        self.min_request_interval = min_request_interval
        self.last_request_time = 0.0
        self._logger = logging.getLogger(__name__)
        self.client = None

        if openalgo_api is None:
            self._logger.warning(
                "OpenAlgo package not available; install openalgo to fetch data."
            )
            return

        if not self.api_key:
            self._logger.warning("OPENALGO_API_KEY not set; data fetches will fail.")
            return

        self.client = openalgo_api(api_key=self.api_key, host=self.base_url)

    def _rate_limit(self) -> None:
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
    ) -> list[OHLCVCandle]:
        if self.client is None:
            raise RuntimeError("OpenAlgo client not configured; set OPENALGO_API_KEY.")

        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "D",
            "1w": "W",
            "1M": "M",
        }
        interval = interval_map[timeframe]

        start_dt = datetime.utcfromtimestamp(start_epoch)
        end_dt = datetime.utcfromtimestamp(end_epoch)
        self._rate_limit()
        try:
            response = self.client.history(
                symbol=ticker,
                exchange=self.exchange,
                interval=interval,
                start_date=start_dt.strftime("%Y-%m-%d"),
                end_date=end_dt.strftime("%Y-%m-%d"),
            )
        except Exception as exc:  # pragma: no cover - depends on provider
            self._logger.exception("OpenAlgo history request failed")
            raise RuntimeError("OpenAlgo history request failed") from exc

        if not isinstance(response, pd.DataFrame) or response.empty:
            self._logger.warning(
                "OpenAlgo returned empty response for %s %s %s-%s",
                ticker,
                timeframe,
                start_dt.date(),
                end_dt.date(),
            )
            return []

        candles: list[OHLCVCandle] = []
        for index, row in response.iterrows():
            timestamp = index
            if not isinstance(timestamp, datetime) and "date" in row:
                timestamp = pd.to_datetime(row["date"], errors="coerce")

            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.to_pydatetime()

            if not isinstance(timestamp, datetime):
                continue

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            try:
                candles.append(
                    OHLCVCandle(
                        epoch=int(timestamp.timestamp()),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                self._logger.warning("Invalid candle row skipped: %s", exc)

        return candles
