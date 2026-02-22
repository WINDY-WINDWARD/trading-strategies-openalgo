# Data Warehouse Guide

This guide covers the independent data warehouse package under `data_warehouse/`.
It explains architecture, APIs, UI, storage, and operations.

## Overview

The data warehouse is a standalone sub-application that:
- Stores OpenAlgo OHLCV candles in SQLite.
- Tracks coverage metadata per ticker/timeframe.
- Provides FastAPI endpoints for ingest, retrieval, and jobs.
- Serves a dashboard UI for ingest and review.

## Architecture

Layered structure:
- `data_warehouse/core/`: Gap detection + provider adapter.
- `data_warehouse/schemas/`: Pydantic validation (requests, candles).
- `data_warehouse/db/`: SQLite schema + repository (SQL only).
- `data_warehouse/services/`: Business workflows (add/update/delete/bulk).
- `data_warehouse/api/`: FastAPI app and routes.
- `data_warehouse/ui/`: Jinja templates and routes.

## Data model (SQLite)

Tables:
- `tickers`: unique tickers.
- `ticker_timeframes`: per ticker/timeframe metadata.
- `ohlcv`: candles by ticker/timeframe/epoch.
- `jobs`: async job metadata.

Indexes:
- `idx_ohlcv_ticker_timeframe_epoch`
- `idx_ticker_timeframes_ticker_timeframe`
- `idx_jobs_status`, `idx_jobs_type`

Epoch storage:
- Stored as raw epoch seconds.
- Converted to IST for UI/API display.

## Swagger / OpenAPI quick guide

Once the app is running, open:
- Swagger UI: `http://127.0.0.1:8811/docs`
- ReDoc: `http://127.0.0.1:8811/redoc`

Swagger groups endpoints by tags:
- `data-warehouse`: ingest, retrieval, metadata, jobs.
- `northbound`: read-oriented endpoints for OHLCV consumers.
- `failed-ingestions`: inspect and retry failed ingestions.

### Base paths

- API base prefix: `/api/data-warehouse`
- UI pages: `/data-warehouse...` (not part of Swagger API operations)

### What each API does

#### data-warehouse tag

- `POST /api/data-warehouse/stocks/add`
	- Queue a new ingestion job for a ticker/timeframe/range.
	- Returns `202` with a `job_id`.

- `POST /api/data-warehouse/stocks/update`
	- Queue incremental update for an existing ticker/timeframe.
	- Returns `202` with job details.

- `POST /api/data-warehouse/stocks/update-all`
	- Queue updates for all tracked ticker/timeframe entries.
	- Use for periodic refreshes.

- `POST /api/data-warehouse/stocks/delete`
	- Queue deletion of stored candle data by criteria.
	- Returns `202` when accepted.

- `POST /api/data-warehouse/stocks/get`
	- Fetch paginated candles for a ticker/timeframe/range.
	- Query params: `limit`, `offset`.

- `GET /api/data-warehouse/stocks/export`
	- Export candles as CSV content in JSON payload (`{"csv": "..."}`).
	- Uses same filters as stock retrieval.

- `POST /api/data-warehouse/stocks/add-bulk`
	- Queue bulk ingestion from JSON rows.
	- Returns one async job.

- `POST /api/data-warehouse/stocks/add-bulk-csv`
	- Upload CSV file and queue ingestion.
	- `multipart/form-data` with `file`.

- `POST /api/data-warehouse/stocks/gap-fill`
	- Queue gap-fill operation to backfill missing periods.
	- Returns `202` job payload.

- `POST /api/data-warehouse/tickers/metadata`
	- Update ticker metadata (`sector`, `company_name`, `exchange`).
	- Synchronous update, returns `200`.

- `GET /api/data-warehouse/jobs/{job_id}`
	- Get one job status (`queued`, `running`, `completed`, `failed`).

- `GET /api/data-warehouse/jobs`
	- List jobs with optional filters: `status`, `job_type`, `limit`, `offset`.

#### northbound tag

- `GET /api/data-warehouse/ohlcv`
	- Consumer-friendly OHLCV feed by `ticker` and `timeframe`.
	- Optional `timerange` supports `dd-mm-yyyy` dates.

- `GET /api/data-warehouse/tickers`
	- List available tickers and timeframes.
	- Useful for discovery before requesting OHLCV.

#### failed-ingestions tag

- `GET /api/data-warehouse/failed-ingestions`
	- List failed (or filtered) ingestion records.
	- Supports `status`, `limit`, and `offset`.

- `POST /api/data-warehouse/failed-ingestions/{failed_id}/retry`
	- Retry a specific failed ingestion with new `start_epoch` and `end_epoch`.
	- Returns `202` with new retry job payload.

### Swagger usage workflow

1. Open `/docs` and expand a tag.
2. Click an endpoint and select **Try it out**.
3. Fill body/query/path fields shown by schema.
4. Execute and inspect response + status code.
5. For async endpoints (`202`), poll `/api/data-warehouse/jobs/{job_id}`.

## UI

Routes:
- `/data-warehouse` dashboard
- `/data-warehouse/tickers/{ticker}?timeframe=...` ticker view

Dashboard:
- Add/Update/Delete forms (HTMX)
- Bulk CSV upload
- Job history with pagination

Ticker view:
- Candlestick chart (Lightweight Charts)
- Metadata (last updated, range start/end)
- Timeframe selector
- Date range filter (start/end dates)
- Paginated OHLCV table + CSV export

## Jobs

Jobs are persisted to SQLite.
Fields include `job_id`, `job_type`, `status`, timestamps, and extra metadata.

Typical states:
- `queued`, `running`, `completed`, `failed`

## CSV format (bulk ingest)

You can use a friendlier format with dates (recommended), or the legacy range JSON.

Option A: date columns (recommended)
```csv
ticker,timeframe,start_date,end_date
RELIANCE,1d,2024-01-01,2024-06-30
IDFCFIRSTB,1h,2024-02-01,2024-02-15
```

Option B: range JSON (legacy)
```csv
ticker,timeframe,range
RELIANCE,1d,"{""start_epoch"":1704067200,""end_epoch"":1719705600}"
```

Notes:
- `timeframe` must be one of: `1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M`.
- If `start_date`/`end_date` are provided, they override `range`.
- If no range is provided, the default last-1-year range is used.

## OpenAlgo configuration

Environment variables:
- `OPENALGO_API_KEY`
- `OPENALGO_BASE_URL` (default `http://127.0.0.1:8800`)
- `OPENALGO_EXCHANGE` (default `NSE`)

## Logging configuration

Environment variables (optional):
- `DW_LOG_LEVEL` (default `INFO`): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `DW_LOG_FILE` (default: none): If set, logs are written to this rotating file (e.g., `logs/data_warehouse.log`)
- `DW_LOG_MAX_BYTES` (default `10485760`): Max size per log file before rotation (10MB)
- `DW_LOG_BACKUP_COUNT` (default `5`): Number of backup log files to keep

Examples:
```bash
# Console only, DEBUG level
DW_LOG_LEVEL=DEBUG uvicorn data_warehouse.data_warehouse:app --reload --port 8811

# Console + file logging
DW_LOG_FILE=logs/data_warehouse.log uvicorn data_warehouse.data_warehouse:app --reload --port 8811

# Debug level with 100MB file rotation, 10 backups
DW_LOG_LEVEL=DEBUG DW_LOG_FILE=logs/data_warehouse.log DW_LOG_MAX_BYTES=104857600 DW_LOG_BACKUP_COUNT=10 uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

## Running the app

```bash
conda run -n trade uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

Open:
- `http://127.0.0.1:8811/` (redirects to `/data-warehouse`)
- `http://127.0.0.1:8811/docs` (Swagger UI)
- `http://127.0.0.1:8811/redoc` (ReDoc)

## Testing

Data-warehouse tests run against a temporary DB:
- `DW_DB_PATH` set to temp file
- `DW_TESTING=1` uses a fake provider

Run:
```bash
conda run -n trade pytest tests/data_warehouse -q
```

## Error handling

Errors are handled consistently across layers:
- Repository wraps SQLite errors as `RepositoryError`.
- Provider errors are wrapped as `ProviderError`.
- API returns clean HTTP errors and logs details.
- UI surfaces failures via job status.
