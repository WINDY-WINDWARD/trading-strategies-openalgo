# Data Warehouse System - Complete Reference

**Last Updated:** 2026-02-22

## Overview

The Data Warehouse is a standalone sub-application (`data_warehouse/`) that provides a complete system for archiving and managing OpenAlgo OHLCV (candlestick) market data in SQLite. It includes:

- **Independent package structure** with layered architecture (API, Services, Core, Database, Schemas)
- **FastAPI REST API** for data ingestion, retrieval, and job management
- **SQLite database** with optimized schema for efficient time-series queries
- **Smart gap detection** to identify and fill missing data ranges automatically
- **Async job processing** with persistent status tracking
- **Web dashboard UI** for data management and monitoring

---

## Architecture

### Layer Organization

The system follows a layered architecture:

```
HTTP Requests
    ↓
API Layer (FastAPI routes)
    ↓
Service Layer (Business workflows & coordination)
    ↓
Core Layer (Gap detection, Provider adapters)
    ↓
Database Layer (Repository pattern, SQL operations)
    ↓
SQLite Database
```

### Directory Structure

```
data_warehouse/
├── __init__.py                          # Package initialization
├── data_warehouse.py                    # FastAPI app factory & entry point
├── logging_config.py                    # Logging configuration
│
├── api/                                 # HTTP API layer
│   ├── __init__.py
│   ├── api.py                          # FastAPI app creation & error handlers
│   ├── deps.py                         # Dependency injection (service factory)
│   └── routes/
│       ├── __init__.py
│       ├── stocks.py                   # Stock data endpoints (11 endpoints)
│       └── failed_ingestions.py        # Failed ingestion management (2 endpoints)
│
├── services/                            # Business logic orchestration
│   ├── __init__.py
│   └── warehouse_service.py            # WarehouseService (main coordinator)
│                                        # JobStore (persistent job tracking)
│
├── core/                                # Domain-specific logic
│   ├── __init__.py
│   ├── gap_detection.py                # Gap detection & timeframe mapping
│   ├── openalgo_client.py              # OpenAlgo API client wrapper
│   └── errors.py                       # Custom exception classes
│
├── db/                                  # Data persistence layer
│   ├── __init__.py
│   ├── db.py                           # Schema initialization & connection
│   └── repository.py                   # WarehouseRepository (all SQL)
│
├── schemas/                             # Pydantic validation models
│   ├── __init__.py
│   ├── ohlcv_data.py                   # OHLCVCandle model
│   ├── requests.py                     # Request payloads & validators
│   └── ticker_data.py                  # Ticker-related schemas
│
└── ui/                                  # Web dashboard
    ├── __init__.py
    ├── ui.py                           # UI routes & template rendering
    └── templates/
        ├── dashboard.html              # Main dashboard page
        └── ticker_view.html            # Ticker details & chart view
```

---

## Database Schema

### PRAGMA Configuration

```sql
PRAGMA foreign_keys = ON;               -- Enforce referential integrity
PRAGMA journal_mode = WAL;              -- Write-Ahead Logging for concurrency
```

### Tables

#### 1. `tickers`
Stores metadata for each ticker symbol.

```sql
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    sector TEXT,
    company_name TEXT,
    exchange TEXT
);
```

#### 2. `ticker_timeframes`
Tracks coverage metadata per ticker-timeframe combination.

```sql
CREATE TABLE ticker_timeframes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    last_updated_epoch INTEGER,
    current_range_start_epoch NUMERIC,
    current_range_end_epoch NUMERIC,
    
    UNIQUE (ticker_id, timeframe),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);
```

**Fields:**
- `last_updated_epoch`: Last candle epoch successfully stored
- `current_range_start_epoch`: Earliest epoch in stored data
- `current_range_end_epoch`: Latest epoch in stored data

#### 3. `ohlcv`
Stores candlestick OHLCV data.

```sql
CREATE TABLE ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    epoch NUMERIC NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume INTEGER NOT NULL,
    
    UNIQUE (ticker_id, timeframe, epoch),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);
```

**Note:** Epoch is stored as raw seconds (no timezone conversion at DB level).

#### 4. `jobs`
Persistent job metadata for async operations.

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    result TEXT,
    error TEXT,
    metadata TEXT
);
```

**Fields:**
- `job_type`: `add`, `update`, `update_all`, `bulk_add`, `delete`, `gap_fill`
- `status`: `queued`, `running`, `completed`, `failed`
- `metadata`: JSON payload (e.g., request parameters, processing stats)

#### 5. `failed_ingestions`
Tracks failed data fetch attempts for retry management.

```sql
CREATE TABLE failed_ingestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    error_reason TEXT,
    epochs_requested TEXT,
    retry_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'failed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes

| Index | Purpose |
|-------|---------|
| `idx_ohlcv_ticker_timeframe_epoch` | Fast range queries on (ticker, timeframe, epoch) |
| `idx_ticker_timeframes_ticker_timeframe` | Quick lookup of ticker-timeframe metadata |
| `idx_jobs_status` | Filter jobs by status |
| `idx_jobs_type` | Filter jobs by type |

---

## Supported Timeframes

All operations accept timeframes from this list:

| Timeframe | Duration |
|-----------|----------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `1h` | 1 hour |
| `4h` | 4 hours |
| `1d` | 1 day |
| `1w` | 1 week |
| `1M` | 1 month |

---

## API Endpoints

Base path: `/api/data-warehouse`

### Stock Data Management

#### 1. Add Stock Data
```
POST /stocks/add
```

**Request:**
```json
{
    "ticker": "RELIANCE",
    "timeframe": "1d",
    "range": {
        "start_epoch": 1704067200,
        "end_epoch": 1719705600
    }
}
```

**Response:**
```json
{
    "job_id": "add-1708601234-abc123",
    "status": "queued",
    "job_type": "add",
    "created_at": "2026-02-22T10:30:00"
}
```

**Behavior:**
- Returns immediately with job ID (async processing)
- Detects gaps in requested range and fetches only missing data
- Skips if full range already exists (short-circuits)
- Uses upsert logic to handle overlapping candles
- Updates `ticker_timeframes` metadata

#### 2. Update Stock Data
```
POST /stocks/update
```

**Request:**
```json
{
    "ticker": "RELIANCE",
    "timeframe": "1d"
}
```

**Behavior:**
- Finds last stored epoch for ticker-timeframe
- Fetches and stores data from that point to present
- Returns job metadata

#### 3. Update All Stocks
```
POST /stocks/update-all
```

**Request:**
```json
{
    "timeframe": "1d"
}
```

**Behavior:**
- Updates all stored tickers for the specified timeframe
- Processed as single async job
- Ideal for scheduled refresh operations

#### 4. Delete Stock Data
```
POST /stocks/delete
```

**Request:**
```json
{
    "ticker": "RELIANCE",
    "timeframe": "1d",
    "range": {
        "start_epoch": 1704067200,
        "end_epoch": 1719705600
    }
}
```

**Behavior:**
- Deletes candles matching ticker + timeframe + range
- If no range provided, deletes all data for ticker-timeframe
- Returns job metadata

#### 5. Get Stock Data
```
POST /stocks/get
```

**Request:**
```json
{
    "ticker": "RELIANCE",
    "timeframe": "1d",
    "range": {
        "start_epoch": 1704067200,
        "end_epoch": 1719705600
    },
    "limit": 100,
    "offset": 0
}
```

**Response:**
```json
{
    "ticker": "RELIANCE",
    "timeframe": "1d",
    "total": 150,
    "offset": 0,
    "limit": 100,
    "candles": [
        {
            "epoch": 1704067200,
            "open": 2750.25,
            "high": 2780.50,
            "low": 2745.00,
            "close": 2775.75,
            "volume": 5000000
        }
    ]
}
```

**Behavior:**
- Returns paginated candle data
- Sorted by epoch ascending
- Converts epoch to IST display format

#### 6. Export Stock Data
```
GET /stocks/export?ticker=RELIANCE&timeframe=1d
```

**Response:** CSV format
```csv
epoch,datetime_ist,open,high,low,close,volume
1704067200,2024-01-01 05:30:00,2750.25,2780.50,2745.00,2775.75,5000000
```

### Bulk Operations

#### 7. Bulk Add (JSON)
```
POST /stocks/add-bulk
```

**Request:**
```json
{
    "rows": [
        {
            "ticker": "RELIANCE",
            "timeframe": "1d",
            "range": {"start_epoch": 1704067200, "end_epoch": 1719705600}
        },
        {
            "ticker": "TCS",
            "timeframe": "1h",
            "range": {"start_epoch": 1704067200, "end_epoch": 1704153600}
        }
    ]
}
```

**Behavior:**
- Processes each row independently (best-effort)
- Failed rows don't block other rows
- Logged in `failed_ingestions` table
- Single async job with detailed error tracking

#### 8. Bulk Add (CSV Upload)
```
POST /stocks/add-bulk-csv
Content-Type: multipart/form-data
```

**CSV Format (recommended):**
```csv
ticker,timeframe,start_date,end_date
RELIANCE,1d,2024-01-01,2024-06-30
TCS,1h,2024-02-01,2024-02-15
INFY,5m,2024-02-20,2024-02-22
```

**CSV Format (legacy with epochs):**
```csv
ticker,timeframe,range
RELIANCE,1d,"{""start_epoch"":1704067200,""end_epoch"":1719705600}"
```

**Behavior:**
- Entire CSV processed as single transaction
- Rollback on failure (atomic operation)
- Returns single job ID for tracking
- CSV rows parsed and validated before insertion

#### 9. Gap Fill
```
POST /stocks/gap-fill
```

**Request:**
```json
{
    "timeframe": "1d"
}
```

**Response:**
```json
{
    "job_id": "gap-fill-1708601234-abc123",
    "status": "queued",
    "job_type": "gap_fill"
}
```

**Behavior:**
- Analyzes all tickers for specified timeframe
- Detects gaps in each ticker's data
- Fetches and fills identified gaps asynchronously
- Updates `ticker_timeframes` ranges

### Ticker Metadata

#### 10. Update Ticker Metadata
```
POST /tickers/metadata
```

**Request:**
```json
{
    "ticker": "RELIANCE",
    "sector": "Energy",
    "company_name": "Reliance Industries Limited",
    "exchange": "NSE"
}
```

### Job Management

#### 11. Get Job Status
```
GET /jobs/{job_id}
```

**Response:**
```json
{
    "job_id": "add-1708601234-abc123",
    "job_type": "add",
    "status": "completed",
    "created_at": "2026-02-22T10:30:00",
    "updated_at": "2026-02-22T10:35:45",
    "completed_at": "2026-02-22T10:35:45",
    "result": {
        "candles_inserted": 150,
        "gaps_filled": 2,
        "duration_seconds": 5.45
    },
    "error": null
}
```

#### 12. List Jobs
```
GET /jobs?status=completed&job_type=add&limit=50&offset=0
```

**Response:**
```json
{
    "total": 120,
    "offset": 0,
    "limit": 50,
    "jobs": [
        {
            "job_id": "add-1708601234-abc123",
            "job_type": "add",
            "status": "completed",
            "created_at": "2026-02-22T10:30:00",
            "updated_at": "2026-02-22T10:35:45"
        }
    ]
}
```

### Failed Ingestions Management

#### 13. List Failed Ingestions
```
GET /failed-ingestions?status=failed&limit=20&offset=0
```

**Response:**
```json
{
    "total": 5,
    "offset": 0,
    "limit": 20,
    "failures": [
        {
            "id": 1,
            "ticker": "UNKNOWN_TICKER",
            "timeframe": "1d",
            "error_reason": "Ticker not found in OpenAlgo",
            "retry_count": 2,
            "status": "failed",
            "created_at": "2026-02-22T10:00:00",
            "updated_at": "2026-02-22T10:15:00"
        }
    ]
}
```

#### 14. Retry Failed Ingestion
```
POST /failed-ingestions/{failed_id}/retry
```

**Response:**
```json
{
    "job_id": "add-1708601234-retry",
    "status": "queued",
    "message": "Retry job created"
}
```

---

## Service Layer

### WarehouseService

Main service class coordinating all operations.

**Key Methods:**
- `enqueue_add()` - Queue add operation
- `enqueue_update()` - Queue update operation
- `enqueue_update_all()` - Queue bulk update
- `enqueue_bulk_add()` - Queue bulk JSON add
- `enqueue_bulk_csv()` - Queue CSV import
- `enqueue_gap_fill()` - Queue gap fill
- `enqueue_delete()` - Queue delete operation
- `process_add()` - Execute add (background)
- `process_update()` - Execute update (background)
- `process_bulk_add()` - Execute bulk add (background)
- `process_gap_fill()` - Execute gap fill (background)
- `get_stock_data()` - Retrieve candles (sync)
- `get_stock_data_page()` - Retrieve paginated candles (sync)
- `get_job()` - Get job status
- `list_jobs()` - List jobs with filters
- `list_failed_ingestions()` - List failures
- `count_failed_ingestions()` - Count failures
- `retry_failed_ingestion()` - Retry failed fetch

### JobStore

Persistent job state tracking.

**Methods:**
- `create()` - Create new job record
- `update()` - Update job status/metadata
- `get()` - Retrieve job by ID
- `list()` - List jobs with filtering

---

## Core Components

### Gap Detection (`core/gap_detection.py`)

**Function:** `detect_missing_ranges()`

Identifies gaps in time-series data by comparing expected vs. actual candles.

**Features:**
- Accounts for market holidays and weekends
- Returns list of (start_epoch, end_epoch) tuples for missing ranges
- Supports all timeframes with correct interval mapping
- Internal and boundary gap detection

**Timeframe Mapping:**
```python
TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000  # 30 days
}
```

### OpenAlgo Client (`core/openalgo_client.py`)

**Class:** `OpenAlgoClient`

Wrapper for OpenAlgo historical data API.

**Features:**
- Configurable base URL and API key
- Rate limiting with backoff strategy
- Batch processing support
- Automatic retry on transient failures
- Candle response normalization

**Configuration:**
- `OPENALGO_API_KEY` (required for production)
- `OPENALGO_BASE_URL` (default: `http://127.0.0.1:8800`)
- `OPENALGO_EXCHANGE` (default: `NSE`)

### Error Handling (`core/errors.py`)

**Hierarchy:**
```
DataWarehouseError (base)
├── RepositoryError (database layer)
└── ProviderError (data provider layer)
```

---

## Repository Pattern (`db/repository.py`)

**Class:** `WarehouseRepository`

Encapsulates all SQL operations.

**Ticker Operations:**
- `get_ticker_id()` - Get ticker ID by symbol
- `insert_ticker()` - Create new ticker record
- `list_tickers()` - Get all tickers
- `update_ticker_metadata()` - Update ticker info

**OHLCV Operations:**
- `insert_ohlcv_batch()` - Batch insert candles (upsert on conflict)
- `get_ohlcv()` - Retrieve candles by range
- `count_ohlcv()` - Count candles in range
- `delete_ohlcv()` - Delete candles by range
- `get_last_epoch()` - Get last stored epoch for ticker-timeframe

**Metadata Operations:**
- `insert_ticker_timeframe()` - Create timeframe tracking record
- `update_ticker_timeframe()` - Update coverage metadata
- `get_ticker_timeframe()` - Get timeframe metadata

**Batch Operations:**
- `insert_tickers_batch()` - Create multiple tickers
- `insert_ohlcv_transaction()` - Insert with explicit transaction

---

## Configuration

### Environment Variables

#### Database
```bash
DW_DB_PATH=/path/to/database.db      # Default: data_warehouse/db/tickerData.db
DW_TESTING=1                          # Enable fake provider (for testing only)
```

#### OpenAlgo Provider
```bash
OPENALGO_API_KEY=your_api_key         # Required for production
OPENALGO_BASE_URL=http://127.0.0.1:8800
OPENALGO_EXCHANGE=NSE
```

#### Logging
```bash
DW_LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR, CRITICAL
DW_LOG_FILE=logs/data_warehouse.log   # Optional; if set, logs to rotating file
DW_LOG_MAX_BYTES=10485760             # 10MB default
DW_LOG_BACKUP_COUNT=5                 # Keep 5 backup files
```

### Example Startup Commands

**Development (console logging):**
```bash
conda run -n trade uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

**With debug logging:**
```bash
DW_LOG_LEVEL=DEBUG conda run -n trade uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

**With file logging:**
```bash
DW_LOG_FILE=logs/data_warehouse.log conda run -n trade uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

---

## Web Dashboard

### Routes

- `GET /data-warehouse` - Main dashboard
- `GET /data-warehouse/manage-tickers` - Ticker management
- `GET /data-warehouse/tickers/{ticker}?timeframe=1d` - Ticker details

### Dashboard Features

**Add/Update/Delete Forms:**
- HTMX-powered forms for ticker operations
- Real-time form validation
- Inline error messages

**Bulk CSV Upload:**
- Drag-and-drop CSV file upload
- Format validation
- Progress tracking

**Job History Panel:**
- List jobs with status filtering
- Pagination and sorting
- Auto-polling for job updates (every 2 seconds)
- Status badges (queued, running, completed, failed)

### Ticker View Features

**Chart:**
- Lightweight Charts candlestick visualization
- Zoom and pan controls
- Timeframe switcher

**Metadata Panel:**
- Last updated timestamp (IST)
- Data range (start/end dates)
- Total candles stored

**OHLCV Table:**
- Paginated table view
- Epoch converted to IST dates
- CSV export button
- Sortable columns

---

## Data Integrity & Consistency

### Upsert Strategy

All candle inserts use `INSERT ... ON CONFLICT` to handle overlapping data:

```sql
INSERT INTO ohlcv (ticker_id, timeframe, epoch, open, high, low, close, volume)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ticker_id, timeframe, epoch) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume;
```

### Gap Detection Logic

1. Calculate expected candles: `(end_epoch - start_epoch) / timeframe_seconds`
2. Count actual candles in range
3. If less than expected:
   - Find missing ranges by scanning stored epochs
   - Skip weekends/holidays (for daily timeframes)
4. Return list of gap ranges for fetching

### Transaction Management

- Bulk CSV imports wrapped in single transaction
- Rollback on any row failure (atomic)
- Bulk JSON uses row-level best effort (individual failures logged)

---

## Testing

### Test Files

- `tests/data_warehouse/test_schemas.py` - Pydantic model validation
- `tests/data_warehouse/test_gap_detection.py` - Gap detection logic
- `tests/data_warehouse/test_api_contract.py` - API endpoint contracts
- `tests/data_warehouse/test_repository.py` - Database operations
- `tests/data_warehouse/test_service.py` - Service layer logic

### Running Tests

```bash
# All data warehouse tests
conda run -n trade pytest tests/data_warehouse -q

# Specific test file
conda run -n trade pytest tests/data_warehouse/test_schemas.py -q

# Specific test
conda run -n trade pytest tests/data_warehouse/test_api_contract.py::test_add_stock -q
```

### Test Configuration

Tests use:
- Temporary SQLite database (in-memory or temp file)
- `DW_TESTING=1` environment flag for fake provider
- Fake OpenAlgo client returning synthetic candles
- No actual API calls to external services

---

## Performance Considerations

### Indexes

The schema includes optimal indexes for:
- `(ticker_id, timeframe, epoch)` - Fast range queries
- `(ticker_id, timeframe)` - Quick metadata lookups
- Job status/type filtering

### Batch Operations

- CSV bulk import processes entire file as transaction
- JSON bulk add processes rows independently
- Gap fills processed per ticker-timeframe (parallel internally possible)

### SQLite Optimizations

- WAL (Write-Ahead Logging) for better concurrency
- Foreign keys enforced for data integrity
- PRAGMA settings optimized for time-series data

---

## Error Handling

### Exception Hierarchy

```python
DataWarehouseError                     # Base exception
├── RepositoryError                   # Database layer
└── ProviderError                     # Data provider
```

### API Error Responses

```json
{
    "detail": "Human-readable error message",
    "status": 400,
    "timestamp": "2026-02-22T10:30:00"
}
```

### Failed Ingestions Tracking

Failed fetches are logged to `failed_ingestions` table with:
- Ticker and timeframe
- Error reason
- Requested epoch ranges
- Retry count
- Status (failed/retried)

---

## Key Design Patterns

1. **Layered Architecture** - Clean separation of concerns (API → Service → Core → DB)
2. **Repository Pattern** - All SQL isolated in repository layer
3. **Dependency Injection** - FastAPI dependencies for loose coupling
4. **Job Queue Pattern** - Async operations with persistent status tracking
5. **Upsert-on-Conflict** - Handle overlapping data gracefully
6. **Gap Detection** - Efficient missing data identification
7. **Transaction Management** - Atomic bulk operations with rollback

---

## Integration Points

### With OpenAlgo

The `OpenAlgoClient` class handles:
- Authentication via `OPENALGO_API_KEY`
- Historical candle fetching
- Rate limiting
- Retry logic
- Response normalization to `OHLCVCandle` schema

### With FastAPI

- Exception handlers for consistent error responses
- Dependency injection for service initialization
- Background tasks for async operations
- CORS support if needed

### With SQLite

- Connection pooling via `sqlite3` standard library
- WAL mode for concurrent access
- Transaction management for data consistency

---

## Deployment

### Standalone Server

```bash
uvicorn data_warehouse.data_warehouse:app --host 0.0.0.0 --port 8811
```

### With Gunicorn (Production)

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker data_warehouse.data_warehouse:app --port 8811
```

### Environment Setup

1. Activate conda environment: `conda activate trade`
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables (see Configuration section)
4. Initialize database (automatic on first run)
5. Start server

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Python files** | 23 |
| **Main modules** | 6 |
| **API endpoints** | 14 |
| **Database tables** | 5 |
| **Custom exceptions** | 3 |
| **Supported timeframes** | 8 |
| **Request schemas** | 9+ |
| **Core services** | 2 |
| **UI routes** | 3+ |

---

## Related Documentation

- **Requirements & Initial Design:** `docs/Data_warehouse_init.md`
- **Implementation Handoff Notes:** `docs/DATA_WAREHOUSE_HANDOFF.md`
- **Review Summary:** `docs/DATA_WAREHOUSE_REVIEW_SUMMARY.md`
- **Quick Start Guide:** `docs/QUICK_START_GUIDE.md`

---

## Notes for Future Development

1. **OpenAlgo Integration**: Provider client is production-ready but should be tested against live OpenAlgo instance
2. **UI Enhancements**: Dashboard is functional; consider adding export scheduling and advanced charting
3. **Performance**: For very large datasets (millions of candles), consider:
   - Implementing data tiering (archive old data)
   - Adding query result caching
   - Using read replicas for analytics
4. **Monitoring**: Add metrics collection (API latency, gap fill duration, error rates)
5. **Scaling**: Current SQLite is suitable for single-server; consider PostgreSQL if multi-server deployment needed

