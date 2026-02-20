from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..api.deps import get_service
from ..core.errors import RepositoryError
from ..schemas.requests import EpochRange, GetStockRequest, Timeframe

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _format_epoch(value: int | None) -> str:
    if not value:
        return "-"
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .astimezone(ZoneInfo("Asia/Kolkata"))
        .strftime("%Y-%m-%d %H:%M")
    )


templates.env.filters["datetimeformat"] = _format_epoch


@router.get("/data-warehouse", response_class=HTMLResponse)
def dashboard(request: Request):
    service = get_service()
    try:
        tickers = service.list_tickers()
        stats = service.get_storage_stats()
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    ist = ZoneInfo("Asia/Kolkata")
    min_epoch = stats.get("min_epoch")
    max_epoch = stats.get("max_epoch")
    stats_display = {
        "ticker_count": stats.get("ticker_count", 0),
        "candle_count": stats.get("candle_count", 0),
        "timeframe_count": stats.get("timeframe_count", 0),
        "min_ist": datetime.fromtimestamp(min_epoch, tz=timezone.utc)
        .astimezone(ist)
        .strftime("%Y-%m-%d")
        if min_epoch
        else "-",
        "max_ist": datetime.fromtimestamp(max_epoch, tz=timezone.utc)
        .astimezone(ist)
        .strftime("%Y-%m-%d")
        if max_epoch
        else "-",
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "tickers": tickers, "stats": stats_display},
    )


@router.get("/data-warehouse/fragments/jobs", response_class=HTMLResponse)
def jobs_fragment(
    request: Request, status: str | None = None, job_type: str | None = None
):
    service = get_service()
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 10))
    offset = max(page - 1, 0) * limit
    try:
        jobs = service.list_jobs(
            status=status, job_type=job_type, limit=limit, offset=offset
        )
        total = service.count_jobs(status=status, job_type=job_type)
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    total_pages = max((total + limit - 1) // limit, 1)
    active = [job for job in jobs if job.get("status") in {"queued", "running"}]
    return templates.TemplateResponse(
        "fragments/jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "active": active,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "limit": limit,
        },
    )


@router.get("/data-warehouse/tickers/{ticker}", response_class=HTMLResponse)
def ticker_view(request: Request, ticker: str, timeframe: Timeframe = "1d"):
    service = get_service()
    available_timeframes = service.list_timeframes_for_ticker(ticker)
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 50))
    offset = max(page - 1, 0) * limit
    start_epoch = request.query_params.get("start_epoch")
    end_epoch = request.query_params.get("end_epoch")
    range_value = None
    if start_epoch and end_epoch:
        if "-" in start_epoch and "-" in end_epoch:
            start_date = datetime.strptime(start_epoch, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_epoch, "%Y-%m-%d").date()
            start_ts = int(
                datetime.combine(start_date, datetime.min.time()).timestamp()
            )
            end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())
            range_value = EpochRange(start_epoch=start_ts, end_epoch=end_ts)
        else:
            range_value = EpochRange(
                start_epoch=int(start_epoch), end_epoch=int(end_epoch)
            )
    request_payload = GetStockRequest(
        ticker=ticker, timeframe=timeframe, range=range_value
    )
    try:
        payload = service.get_stock_data_page(
            request=request_payload,
            limit=limit,
            offset=offset,
        )
        chart_payload = service.get_stock_data_page(
            request=request_payload,
            limit=500,
            offset=0,
        )
        if not payload.get("candles") and payload.get("meta"):
            meta = payload["meta"]
            if meta.get("current_range_start_epoch") and meta.get(
                "current_range_end_epoch"
            ):
                fallback_range = EpochRange(
                    start_epoch=int(meta["current_range_start_epoch"]),
                    end_epoch=int(meta["current_range_end_epoch"]),
                )
                fallback_request = GetStockRequest(
                    ticker=ticker, timeframe=timeframe, range=fallback_range
                )
                payload = service.get_stock_data_page(
                    request=fallback_request,
                    limit=limit,
                    offset=offset,
                )
                chart_payload = service.get_stock_data_page(
                    request=fallback_request,
                    limit=500,
                    offset=0,
                )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
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
            "range": payload.get("range"),
            "available_timeframes": available_timeframes,
        },
    )


@router.get("/data-warehouse/failed-ingestions", response_class=HTMLResponse)
def failed_ingestions_view(request: Request):
    service = get_service()
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 50))
    offset = max(page - 1, 0) * limit
    try:
        failures = service.list_failed_ingestions(status="failed", limit=limit, offset=offset)
        total = service.count_failed_ingestions(status="failed")
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    total_pages = max((total + limit - 1) // limit, 1)
    ist = ZoneInfo("Asia/Kolkata")
    for failure in failures:
        if failure.get("attempted_at"):
            failure["attempted_at_ist"] = (
                datetime.fromtimestamp(failure["attempted_at"], tz=timezone.utc)
                .astimezone(ist)
                .strftime("%Y-%m-%d %H:%M:%S")
            )
        if failure.get("requested_start_epoch"):
            failure["start_date"] = (
                datetime.fromtimestamp(failure["requested_start_epoch"], tz=timezone.utc)
                .astimezone(ist)
                .strftime("%Y-%m-%d")
            )
        if failure.get("requested_end_epoch"):
            failure["end_date"] = (
                datetime.fromtimestamp(failure["requested_end_epoch"], tz=timezone.utc)
                .astimezone(ist)
                .strftime("%Y-%m-%d")
            )
    
    return templates.TemplateResponse(
        "failed_ingestions.html",
        {
            "request": request,
            "failures": failures,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "limit": limit,
        },
    )
