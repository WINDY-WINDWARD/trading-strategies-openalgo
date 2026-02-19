# DataWarehouse Architecture

<aside>

**Goal:** Build a **Data Warehouse** sub-application that uses **SQLite** as a local archive for **OpenAlgo OHLCV** data.

</aside>

### Scope

This module must be fully independent from the current app and have its own:

- folder structure
- database layer
- API layer
- UI layer

### Folder Structure (Refined)

```
root
|-- data_warehouse
|-- core
|   |-- __init__.py
|   |-- gap_detection.py         # Finds missing internal intervals
|   |-- openalgo_client.py       # OpenAlgo fetch wrapper
|-- schemas
|   |-- __init__.py
|   |-- ticker_data.py           # Ticker metadata validation
|   |-- ohlcv_data.py            # Candle validation
|   |-- requests.py              # API request models
|-- services
|   |-- __init__.py
|   |-- warehouse_service.py     # Coordinates API, core, and DB
|-- db
|   |-- __init__.py
|   |-- db.py                    # Connection/session helpers
|   |-- repository.py            # Pure SQL operations
|   |-- tickerData.db
|-- api
|   |-- __init__.py
|   |-- api.py                   # FastAPI app + endpoint wiring
|   |-- routes
|   |   |-- __init__.py
|   |   |-- stocks.py
|   |-- deps.py
|-- ui
|   |-- templates
|   |   |-- __init__.py
|   |   |-- dashboard.html       # View all tickers and metadata
|   |   |-- ticker_view.html     # OHLCV chart + ticker details
|   |-- __init__.py
|   |-- ui.py
|-- __init__.py
|-- data_warehouse.py            # Main app factory and entry point
```

### Layer Responsibilities

- `api/`: HTTP layer only. Handles request and response logic and schedules background work.
- `services/`: Business orchestration. Add, update, delete, and bulk processing workflows.
- `core/`: Domain logic. Gap detection and provider adapters.
- `db/`: Repository pattern and SQL only. No endpoint logic.
- `schemas/`: Pydantic validation for request payloads, CSV rows, and provider responses.

---

### Storage Schema

The SQLite database will have the following schema:

**Timestamp storage and display**

- OpenAlgo timestamps arrive as **epoch** values.
- Store the epoch **as-is** in SQLite (recommendation: **epoch seconds** as an `INTEGER`).
- Convert to **IST (Asia/Kolkata)** only when returning data to the UI or rendering charts/tables.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL; -- Enable Write-Ahead Logging for better concurrency

CREATE TABLE tickers (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	ticker TEXT UNIQUE NOT NULL,
	sector TEXT,
	company_name TEXT,
	exchange TEXT
);

CREATE TABLE ticker_timeframes (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	ticker_id INTEGER NOT NULL,
	timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d','1w','1M')),
	last_updated_epoch INTEGER, -- epoch (seconds), as received
	current_range_start_epoch NUMERIC,
	current_range_end_epoch NUMERIC,
	UNIQUE (ticker_id, timeframe),
	FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE TABLE ohlcv (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	ticker_id INTEGER NOT NULL,
	timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d','1w','1M')),
	epoch NUMERIC NOT NULL, -- epoch timestamp (seconds), as received
	open NUMERIC NOT NULL,
	high NUMERIC NOT NULL,
	low NUMERIC NOT NULL,
	close NUMERIC NOT NULL,
	volume INTEGER NOT NULL,
	UNIQUE (ticker_id, timeframe, epoch),
	FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE INDEX idx_ohlcv_ticker_timeframe_epoch
ON ohlcv (ticker_id, timeframe, epoch);

CREATE INDEX idx_ticker_timeframes_ticker_timeframe
ON ticker_timeframes (ticker_id, timeframe);
```

### Database Layer Notes (Performance + Consistency)

- **Timeframe is a first-class key dimension.** All reads and writes must include `ticker + timeframe`.
- Keep the composite index on `ohlcv(ticker_id, timeframe, epoch)` to avoid full table scans for range reads.
- Enforce uniqueness with `UNIQUE (ticker_id, timeframe, epoch)` to prevent duplicate candles during overlapping fetches.
- Track metadata (`last_updated`, `current_range_start`, `current_range_end`) per ticker-timeframe pair using `ticker_timeframes`.
- Add `ON DELETE CASCADE` on foreign keys from `ohlcv` and `ticker_timeframes` to `tickers` if you expect deleting tickers. Otherwise deletions become multi-step and error-prone.

### Upsert-Style Writes

To avoid crashes and duplicate-key failures on overlaps, use upsert-style inserts.

Insert-only (ignore overlaps):

```sql
INSERT OR IGNORE INTO ohlcv (
	ticker_id, timeframe, epoch, open, high, low, close, volume
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
```

Insert-or-update (overwrite on conflict):

```sql
INSERT INTO ohlcv (
	ticker_id, timeframe, epoch, open, high, low, close, volume
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ticker_id, timeframe, epoch) DO UPDATE SET
	open = excluded.open,
	high = excluded.high,
	low = excluded.low,
	close = excluded.close,
	volume = excluded.volume;
```

### Transaction Management

- Wrap multi-row DB operations in `with sqlite3.connect(...) as conn:` blocks.
- For bulk CSV ingest, process each CSV as one transaction, or in controlled chunks, and rollback on failure.
- Never leave partial writes from failed bulk imports.

### Repository Pattern Requirement

- SQL must live in the DB repository layer (`db/repository.py`), not in endpoint handlers.
- API handlers call service methods.
- Services call repository methods (for example: `get_ticker_data`, `insert_ohlcv_batch`, `delete_range`).

### Validation Requirement

- Validate all API payloads and CSV rows using Pydantic models before DB writes.
- Validate OpenAlgo candle payload types, especially numeric OHLCV fields, before insert or upsert.
- Restrict `timeframe` to one of: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M`.

---

### Cross-Cutting API and Data Integrity Rules

- Use smart gap detection for add, get, and update requests. Detect missing internal ranges, not only start and end boundaries.
- Example: If a request range is `2020-01-01` to `2024-12-31` and `2022` is missing, fetch and fill only that gap.
- Run gap detection and storage independently per timeframe.
- Perform write paths (Add, Update, Bulk Add) asynchronously to avoid blocking UI and API threads.
- Use FastAPI `BackgroundTasks`, or an internal worker queue, for long-running fetch and store operations.
- Return job and status metadata for async operations (for example: queued, running, completed, failed).

---

### Required API Endpoints

#### 1) Add Stock Data

Add OHLCV data for a ticker and time range.

**Behavior**

- If ticker data for the requested range already exists, return an “already present” response.
- If the ticker exists but the requested range is only partially available, run smart gap detection and fetch only missing internal and external gaps.
- Insert candles using upsert logic (`INSERT OR IGNORE` or `ON CONFLICT`) to handle overlap safely.
- Execute data fetch and insert in background for large ranges.

**Params**

- `ticker` (required)
- `timeframe` (optional, default: `1d`, allowed: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M`)
- `range` (optional, default: last 1 year from current date)

#### 2) Delete Stock Data

Delete stored OHLCV data for a ticker.

**Behavior**

- Delete data for a specified range, or
- Delete all data for the ticker if no range is provided.

**Params**

- `ticker` (required)
- `timeframe` (optional. If omitted, delete all available timeframes for the ticker in the selected range.)
- `range` (optional)

#### 3) Update Stock Data

Update existing ticker data to the latest available point.

**Behavior**

- Find the last stored timestamp for the ticker.
- Fetch data from that timestamp to the latest from OpenAlgo.
- Store the new records.
- Execute as an async background task for non-trivial updates.

**Params**

- `ticker` (required)
- `timeframe` (optional, default: `1d`, allowed: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M`)

#### 4) Get Stock Data

Return stored OHLCV data for a ticker.

**Params**

- `ticker` (required)
- `timeframe` (optional, default: `1d`, allowed: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M`)
- `range` (optional, default: last 1 year from current date)

#### 5) Add Stock Data (Bulk)

Bulk version of Add Stock Data.

**Behavior**

- Process a CSV file in batch mode.
- Apply the same add logic and validation as single-ticker Add Stock Data.
- Use transaction management so failures rollback cleanly.
- Run as an async background job to keep UI responsive.

**Params**

- CSV file with headers: `ticker`, `timeframe`, `range`

---

### UI Layer Enhancements

- Use a chart-first view in `ticker_view.html` (Plotly.js or Lightweight Charts) instead of large raw tables.
- Keep tabular OHLCV output optional and paginated for diagnostics and export scenarios.
- Use HTMX actions for update and refresh controls to avoid full-page reloads.
- Refresh last-updated timestamp, ingest status, and job state dynamically from API status endpoints.