from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .routes.stocks import router as stocks_router
from ..ui.ui import router as ui_router


def create_app() -> FastAPI:
    app = FastAPI(title="Data Warehouse")

    @app.get("/")
    def root_redirect():
        return RedirectResponse(url="/data-warehouse")

    app.include_router(stocks_router)
    app.include_router(ui_router)
    return app


app = create_app()
