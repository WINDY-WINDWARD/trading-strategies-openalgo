from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import time

import httpx
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
        batch_request_size: int = 1,
        batch_pause_seconds: float = 5.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
    ):
        self.api_key = api_key or os.getenv("OPENALGO_API_KEY")
        self.base_url = base_url or os.getenv(
            "OPENALGO_BASE_URL", "http://127.0.0.1:8800"
        )
        self.exchange = exchange or os.getenv("OPENALGO_EXCHANGE", "NSE")
        self.min_request_interval = min_request_interval
        self.batch_request_size = max(1, batch_request_size)
        self.batch_pause_seconds = max(0.0, batch_pause_seconds)
        self.max_retries = max(1, max_retries)
        self.backoff_base_seconds = max(0.1, backoff_base_seconds)
        self.last_request_time = 0.0
        self.request_count = 0
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

        if (
            self.request_count > 0
            and self.request_count % self.batch_request_size == 0
            and self.batch_pause_seconds > 0
        ):
            time.sleep(self.batch_pause_seconds)

        self.last_request_time = time.time()

    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_epoch: int,
        end_epoch: int,
        exchange: str | None = None,
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
        response = None
        for attempt in range(1, self.max_retries + 1):
            self._rate_limit()
            try:
                response = self.client.history(
                    symbol=ticker,
                    exchange=exchange or self.exchange,
                    interval=interval,
                    start_date=start_dt.strftime("%Y-%m-%d"),
                    end_date=end_dt.strftime("%Y-%m-%d"),
                )
                break
            except Exception as exc:  # pragma: no cover - depends on provider
                if attempt == self.max_retries:
                    self._logger.exception("OpenAlgo history request failed")
                    raise RuntimeError("OpenAlgo history request failed") from exc

                backoff_seconds = self.backoff_base_seconds * (2 ** (attempt - 1))
                self._logger.warning(
                    "OpenAlgo history request failed (attempt %s/%s). Retrying in %.2fs",
                    attempt,
                    self.max_retries,
                    backoff_seconds,
                )
                time.sleep(backoff_seconds)
            finally:
                self.request_count += 1

        if response is None:
            return []

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
                row_data = row.to_dict()
                open_value = float(row_data["open"])
                high_value = float(row_data["high"])
                low_value = float(row_data["low"])
                close_value = float(row_data["close"])
                volume_value = int(row_data["volume"])
                candles.append(
                    OHLCVCandle(
                        epoch=int(timestamp.timestamp()),
                        open=open_value,
                        high=high_value,
                        low=low_value,
                        close=close_value,
                        volume=volume_value,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                self._logger.warning("Invalid candle row skipped: %s", exc)

        return candles

    def search_symbols(self, query: str, exchange: str | None = None) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("OpenAlgo client not configured; set OPENALGO_API_KEY.")

        base_url = (self.base_url or "").rstrip("/")
        if not base_url:
            raise RuntimeError("OpenAlgo base URL not configured.")

        payload = {"apikey": self.api_key, "query": query}
        if exchange:
            payload["exchange"] = exchange

        url = f"{base_url}/api/v1/search"
        try:
            response = httpx.post(url, json=payload, timeout=15.0)
        except httpx.HTTPError as exc:
            self._logger.exception("OpenAlgo search request failed")
            raise RuntimeError("OpenAlgo search request failed") from exc

        if response.status_code != 200:
            self._logger.warning(
                "OpenAlgo search request failed with status %s", response.status_code
            )
            raise RuntimeError("OpenAlgo search request failed")

        data = response.json()
        if data.get("status") != "success":
            message = data.get("message") or "OpenAlgo search failed"
            raise RuntimeError(message)

        results = data.get("data") or []
        if not isinstance(results, list):
            return []
        normalized: list[dict] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "symbol": item.get("symbol"),
                    "brsymbol": item.get("brsymbol"),
                    "name": item.get("name"),
                    "exchange": item.get("exchange"),
                    "brexchange": item.get("brexchange"),
                    "token": item.get("token"),
                    "expiry": item.get("expiry"),
                    "strike": item.get("strike"),
                    "lotsize": item.get("lotsize"),
                    "instrumenttype": item.get("instrumenttype"),
                    "tick_size": item.get("tick_size"),
                }
            )
        return normalized
