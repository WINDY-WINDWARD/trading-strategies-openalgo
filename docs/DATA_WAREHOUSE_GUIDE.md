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

## API endpoints

Base prefix: `/api/data-warehouse`

Stock data:
- `POST /stocks/add` (async job)
- `POST /stocks/update` (async job)
- `POST /stocks/delete` (async job)
- `POST /stocks/get` (paged)
- `GET /stocks/export` (CSV payload)

Bulk ingest:
- `POST /stocks/add-bulk` (JSON rows, async)
- `POST /stocks/add-bulk-csv` (CSV upload, async, transactional)

Jobs:
- `GET /jobs/{job_id}`
- `GET /jobs?status=&job_type=&limit=&offset=`

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

## Running the app

```bash
conda run -n trade uvicorn data_warehouse.data_warehouse:app --reload --port 8811
```

Open:
- `http://127.0.0.1:8811/` (redirects to `/data-warehouse`)

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
