from __future__ import annotations

from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ...schemas.requests import EpochRange, Timeframe
from ...services.warehouse_service import WarehouseService
from ..deps import get_service


router = APIRouter(prefix="/api/data-warehouse", tags=["northbound"])


def _parse_timerange(timerange: str | None, service: WarehouseService) -> EpochRange:
    if not timerange:
        return service.default_range()

    matches = re.findall(r"\b\d{2}-\d{2}-\d{4}\b", timerange)
    if not matches:
        raise ValueError("timerange must include dd-mm-yyyy")
    if len(matches) > 2:
        raise ValueError("timerange must include at most two dates")

    try:
        start_date = datetime.strptime(matches[0], "%d-%m-%Y").date()
    except ValueError as exc:
        raise ValueError("timerange must use dd-mm-yyyy") from exc

    if len(matches) == 1:
        start_epoch = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_epoch = service.clock()
        return EpochRange(start_epoch=start_epoch, end_epoch=end_epoch)

    try:
        end_date = datetime.strptime(matches[1], "%d-%m-%Y").date()
    except ValueError as exc:
        raise ValueError("timerange must use dd-mm-yyyy") from exc

    start_epoch = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_epoch = int(datetime.combine(end_date, datetime.max.time()).timestamp())
    return EpochRange(start_epoch=start_epoch, end_epoch=end_epoch)


@router.get("/ohlcv")
def get_ohlcv(
    ticker: str,
    timeframe: Timeframe,
    timerange: str | None = None,
    service: WarehouseService = Depends(get_service),
):
    try:
        normalized = ticker.strip().upper()
        selected_range = _parse_timerange(timerange, service)
        candles = service.get_ohlcv_range(
            ticker=normalized,
            timeframe=timeframe,
            selected_range=selected_range,
        )
        return JSONResponse(status_code=200, content=candles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tickers")
def list_tickers(service: WarehouseService = Depends(get_service)):
    try:
        payload = service.list_tickers_with_timeframes()
        return JSONResponse(status_code=200, content=payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
