# Data Warehouse Handoff (2026-02-20)

## Context
- Work started from requirements in [docs/Data_warehouse_init.md](docs/Data_warehouse_init.md).
- Implementation approach is TDD-first with a new independent package rooted at [data_warehouse](data_warehouse).
- API/contract choices already locked during implementation:
  - REST endpoints with JSON request bodies
  - epoch-seconds range input (`start_epoch`, `end_epoch`)
  - bulk add policy = row-level best effort
  - async status UX = HTMX polling (not websocket-first)

## What Was Implemented

### 1) New sub-application scaffold
- Created independent package structure under [data_warehouse](data_warehouse):
  - [data_warehouse/api/api.py](data_warehouse/api/api.py)
  - [data_warehouse/api/deps.py](data_warehouse/api/deps.py)
  - [data_warehouse/api/routes/stocks.py](data_warehouse/api/routes/stocks.py)
  - [data_warehouse/core/gap_detection.py](data_warehouse/core/gap_detection.py)
  - [data_warehouse/core/openalgo_client.py](data_warehouse/core/openalgo_client.py)
  - [data_warehouse/db/db.py](data_warehouse/db/db.py)
  - [data_warehouse/db/repository.py](data_warehouse/db/repository.py)
  - [data_warehouse/services/warehouse_service.py](data_warehouse/services/warehouse_service.py)
  - [data_warehouse/schemas/requests.py](data_warehouse/schemas/requests.py)
  - [data_warehouse/schemas/ohlcv_data.py](data_warehouse/schemas/ohlcv_data.py)
  - [data_warehouse/schemas/ticker_data.py](data_warehouse/schemas/ticker_data.py)
  - [data_warehouse/data_warehouse.py](data_warehouse/data_warehouse.py)
  - [data_warehouse/ui/ui.py](data_warehouse/ui/ui.py)
  - [data_warehouse/ui/templates/dashboard.html](data_warehouse/ui/templates/dashboard.html)
  - [data_warehouse/ui/templates/ticker_view.html](data_warehouse/ui/templates/ticker_view.html)

### 2) Initial TDD tests added first
- Added initial tests in [tests/data_warehouse](tests/data_warehouse):
  - [tests/data_warehouse/test_schemas.py](tests/data_warehouse/test_schemas.py)
  - [tests/data_warehouse/test_gap_detection.py](tests/data_warehouse/test_gap_detection.py)
  - [tests/data_warehouse/test_api_contract.py](tests/data_warehouse/test_api_contract.py)

### 3) Core behaviors currently present
- Schema validation for timeframe allow-list and epoch range ordering.
- Gap detection for internal and boundary gaps over fixed interval seconds.
- SQLite schema bootstrap with WAL + foreign keys + required indexes.
- Repository upsert path using ON CONFLICT for `(ticker_id, timeframe, epoch)`.
- API endpoints for add/delete/update/get/add-bulk plus job lookup.
- In-memory job store with `queued/running/completed` state transitions.

## What Is Incomplete / Needs Follow-up

### A) Async execution model is currently synchronous-in-request
- Current `enqueue_*` methods call `process_*` immediately.
- Requirement says write flows should run asynchronously/background and return job metadata promptly.
- Next agent should wire FastAPI `BackgroundTasks` (or queue) in routes and keep service methods side-effect clean.

### B) OpenAlgo provider integration is still stubbed
- [data_warehouse/core/openalgo_client.py](data_warehouse/core/openalgo_client.py) currently returns empty candles.
- Must integrate real OpenAlgo historical fetch and normalize to schema.

### C) DB and service tests are missing
- No repository tests yet for:
  - unique constraints/upsert overwrite behavior
  - index existence checks
  - delete semantics across ticker/timeframe/range combinations
  - ticker_timeframes metadata updates (`last_updated_epoch`, range bounds)
- No service tests yet for:
  - already-present short-circuit
  - internal-gap-only fetch behavior
  - update from last epoch behavior
  - bulk row-level error accounting

### D) API contract not fully aligned to spec edge cases
- `GET` operation is implemented as POST body (`/stocks/get`) by chosen contract.
- Job lifecycle endpoint exists, but no consolidated list/filter endpoint yet.
- IST conversion at response/UI boundary is not implemented yet (epoch stored as-is is done).

### E) UI is placeholder-only
- Templates exist but no chart rendering (Plotly/Lightweight Charts), no HTMX polling fragments, no paginated table diagnostics.

## Test/Validation Status
- Environment checks succeeded (`conda run -n trade python -V` returned Python 3.11.14).
- Full execution of new tests was not completed in this session due interrupted/cancelled test command.
- Current status must be treated as "implementation drafted, test pass status not confirmed".

## Recommended Next TDD Sequence (for next agent)
1. Run only schema + gap tests first and make them green.
2. Add repository tests, then adjust [data_warehouse/db/repository.py](data_warehouse/db/repository.py) for exact SQL semantics.
3. Add service tests with fake provider/repo to lock gap-fill/update/bulk logic.
4. Convert route write paths to true background jobs and add API tests for async semantics.
5. Integrate real OpenAlgo client and add integration-style service tests with provider mocked at transport edge.
6. Add UI status fragment endpoints + HTMX polling + chart-first ticker page.
7. Run formatting/lint/tests per [AGENTS.md](AGENTS.md).

## Commands for Next Agent
- Focused tests:
  - `conda run -n trade pytest tests/data_warehouse/test_schemas.py -q`
  - `conda run -n trade pytest tests/data_warehouse/test_gap_detection.py -q`
  - `conda run -n trade pytest tests/data_warehouse/test_api_contract.py -q`
- After adding DB/service tests:
  - `conda run -n trade pytest tests/data_warehouse -q`
- Style checks:
  - `conda run -n trade black .`
  - `conda run -n trade isort .`
  - `conda run -n trade ruff check .`

## Notes for Safe Continuation
- Preserve independence from existing [app](app) package except shared third-party dependencies.
- Keep SQL in repository layer only; avoid SQL in API routes/services.
- Keep epoch persisted as raw epoch; do IST conversion only when returning UI/API display fields.