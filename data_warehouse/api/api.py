from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from .routes.stocks import router as stocks_router
from .routes.failed_ingestions import router as failed_ingestions_router
from ..ui.ui import router as ui_router


def create_app() -> FastAPI:
    app = FastAPI(title="Data Warehouse")

    logger = logging.getLogger(__name__)

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ):
        logger.warning("HTTP error %s: %s", exc.status_code, exc.detail)
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.warning("Validation error: %s", exc.errors())
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    @app.get("/")
    def root_redirect():
        return RedirectResponse(url="/data-warehouse")

    app.include_router(stocks_router)
    app.include_router(failed_ingestions_router)
    app.include_router(ui_router)
    return app


app = create_app()
