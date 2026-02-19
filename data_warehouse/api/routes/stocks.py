from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import csv
import io

from ...schemas.requests import (
    AddStockRequest,
    BulkAddRequest,
    DeleteStockRequest,
    GetStockRequest,
    UpdateStockRequest,
)
from ...services.warehouse_service import WarehouseService
from ..deps import get_service


router = APIRouter(prefix="/api/data-warehouse", tags=["data-warehouse"])


@router.post("/stocks/add")
def add_stock_data(
    request: AddStockRequest,
    background_tasks: BackgroundTasks,
    service: WarehouseService = Depends(get_service),
):
    job = service.enqueue_add(request)
    background_tasks.add_task(service.process_add, job["job_id"], request)
    return JSONResponse(status_code=202, content=job)


@router.post("/stocks/delete")
def delete_stock_data(
    request: DeleteStockRequest,
    background_tasks: BackgroundTasks,
    service: WarehouseService = Depends(get_service),
):
    job = service.enqueue_delete(request)
    background_tasks.add_task(service.process_delete, job["job_id"], request)
    return JSONResponse(status_code=202, content=job)


@router.post("/stocks/update")
def update_stock_data(
    request: UpdateStockRequest,
    background_tasks: BackgroundTasks,
    service: WarehouseService = Depends(get_service),
):
    job = service.enqueue_update(request)
    background_tasks.add_task(service.process_update, job["job_id"], request)
    return JSONResponse(status_code=202, content=job)


@router.post("/stocks/get")
def get_stock_data(
    request: GetStockRequest,
    limit: int = 500,
    offset: int = 0,
    service: WarehouseService = Depends(get_service),
):
    try:
        payload = service.get_stock_data_page(
            request=request,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(status_code=200, content=payload)


@router.get("/stocks/export")
def export_stock_data(
    request: GetStockRequest = Depends(),
    service: WarehouseService = Depends(get_service),
):
    try:
        payload = service.get_stock_data_page(request=request, limit=10000, offset=0)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["epoch", "timestamp_ist", "open", "high", "low", "close", "volume"]
    )
    for candle in payload["candles"]:
        writer.writerow(
            [
                candle["epoch"],
                candle.get("timestamp_ist"),
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                candle["volume"],
            ]
        )
    return JSONResponse(status_code=200, content={"csv": output.getvalue()})


@router.post("/stocks/add-bulk")
def add_stock_data_bulk(
    request: BulkAddRequest,
    background_tasks: BackgroundTasks,
    service: WarehouseService = Depends(get_service),
):
    job = service.enqueue_bulk_add(request)
    background_tasks.add_task(service.process_bulk_add, job["job_id"], request)
    return JSONResponse(status_code=202, content=job)


@router.post("/stocks/add-bulk-csv")
async def add_stock_data_bulk_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: WarehouseService = Depends(get_service),
):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    rows = []
    for row in reader:
        cleaned = {key: value for key, value in row.items() if key}
        if not cleaned:
            continue
        rows.append(cleaned)
    job = service.job_store.create("bulk_csv")
    background_tasks.add_task(service.process_bulk_csv, job["job_id"], rows)
    return JSONResponse(status_code=202, content=job)


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, service: WarehouseService = Depends(get_service)):
    job = service.get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    return JSONResponse(status_code=200, content=job)


@router.get("/jobs")
def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: WarehouseService = Depends(get_service),
):
    jobs = service.list_jobs(
        status=status, job_type=job_type, limit=limit, offset=offset
    )
    total = service.count_jobs(status=status, job_type=job_type)
    return JSONResponse(status_code=200, content={"jobs": jobs, "total": total})
