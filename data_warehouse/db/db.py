from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    sector TEXT,
    company_name TEXT,
    exchange TEXT
);

CREATE TABLE IF NOT EXISTS ticker_timeframes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d','1w','1M')),
    last_updated_epoch INTEGER,
    current_range_start_epoch NUMERIC,
    current_range_end_epoch NUMERIC,
    UNIQUE (ticker_id, timeframe),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d','1w','1M')),
    epoch NUMERIC NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume INTEGER NOT NULL,
    UNIQUE (ticker_id, timeframe, epoch),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_timeframe_epoch
ON ohlcv (ticker_id, timeframe, epoch);

CREATE INDEX IF NOT EXISTS idx_ticker_timeframes_ticker_timeframe
ON ticker_timeframes (ticker_id, timeframe);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
