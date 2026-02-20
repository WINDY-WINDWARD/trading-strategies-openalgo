"""API routes for managing failed ingestions."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from ...services.warehouse_service import WarehouseService
from ..deps import get_service


router = APIRouter(prefix="/api/data-warehouse", tags=["failed-ingestions"])


@router.get("/failed-ingestions")
def list_failed_ingestions(
    status: str = "failed",
    limit: int = 50,
    offset: int = 0,
    service: WarehouseService = Depends(get_service),
):
    """List failed ingestions with optional filtering and pagination."""
    try:
        failures = service.list_failed_ingestions(
            status=status, limit=limit, offset=offset
        )
        total = service.count_failed_ingestions(status=status)
        return JSONResponse(
            status_code=200,
            content={
                "failures": failures,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/failed-ingestions/{failed_id}/retry")
def retry_failed_ingestion(
    failed_id: int,
    start_epoch: int,
    end_epoch: int,
    background_tasks: BackgroundTasks,
    service: WarehouseService = Depends(get_service),
):
    """Retry a failed ingestion with new time parameters."""
    try:
        failures = service.list_failed_ingestions(status="failed", limit=None)
        failure = next((f for f in failures if f["id"] == failed_id), None)
        if failure is None:
            raise HTTPException(status_code=404, detail="Failed ingestion not found")

        job = service.retry_failed_ingestion(
            failed_id=failed_id,
            ticker=failure["ticker"],
            timeframe=failure["timeframe"],
            start_epoch=start_epoch,
            end_epoch=end_epoch,
        )
        return JSONResponse(status_code=202, content=job)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
