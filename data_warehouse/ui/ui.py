from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..api.deps import get_service
from ..schemas.requests import GetStockRequest, Timeframe

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/data-warehouse", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/data-warehouse/fragments/jobs", response_class=HTMLResponse)
def jobs_fragment(
    request: Request, status: str | None = None, job_type: str | None = None
):
    service = get_service()
    jobs = service.list_jobs(status=status, job_type=job_type)
    active = [job for job in jobs if job.get("status") in {"queued", "running"}]
    return templates.TemplateResponse(
        "fragments/jobs.html",
        {"request": request, "jobs": active},
    )


@router.get("/data-warehouse/tickers/{ticker}", response_class=HTMLResponse)
def ticker_view(request: Request, ticker: str, timeframe: Timeframe = "1d"):
    service = get_service()
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 50))
    offset = max(page - 1, 0) * limit
    payload = service.get_stock_data_page(
        request=GetStockRequest(ticker=ticker, timeframe=timeframe),
        limit=limit,
        offset=offset,
    )
    chart_payload = service.get_stock_data_page(
        request=GetStockRequest(ticker=ticker, timeframe=timeframe),
        limit=500,
        offset=0,
    )
    chart_candles = sorted(
        chart_payload.get("candles", []), key=lambda item: item["epoch"]
    )
    recent_candles = list(reversed(chart_candles))[:6]
    ist = ZoneInfo("Asia/Kolkata")
    meta = payload.get("meta") or {}
    last_updated = meta.get("last_updated_epoch")
    range_start = meta.get("current_range_start_epoch")
    range_end = meta.get("current_range_end_epoch")
    meta_display = {
        "last_updated_ist": datetime.fromtimestamp(last_updated, tz=timezone.utc)
        .astimezone(ist)
        .isoformat()
        if last_updated
        else None,
        "range_start_ist": datetime.fromtimestamp(range_start, tz=timezone.utc)
        .astimezone(ist)
        .isoformat()
        if range_start
        else None,
        "range_end_ist": datetime.fromtimestamp(range_end, tz=timezone.utc)
        .astimezone(ist)
        .isoformat()
        if range_end
        else None,
    }
    return templates.TemplateResponse(
        "ticker_view.html",
        {
            "request": request,
            "ticker": payload["ticker"],
            "timeframe": payload["timeframe"],
            "candles": chart_candles,
            "recent_candles": recent_candles,
            "page_candles": payload["candles"],
            "page": page,
            "limit": limit,
            "total": payload.get("total", 0),
            "meta": meta_display,
        },
    )
