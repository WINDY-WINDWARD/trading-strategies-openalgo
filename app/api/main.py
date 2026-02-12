# app/api/main.py
"""
Main FastAPI application for the backtesting web UI.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..utils.logging_config import setup_logging
from ..utils.config_loader import load_config
from .routes import backtest

# Load configuration and setup logging with config values
try:
    app_config = load_config()
    setup_logging(
        level=app_config.logging.level,
        format_str=app_config.logging.format,
        log_file=app_config.logging.file
    )
except Exception as e:
    # Fallback to basic logging if config loading fails
    setup_logging(level="DEBUG")
    print(f"Warning: Could not load configs/active/config.yaml, using default logging: {e}")

logger = logging.getLogger(__name__)

# Test logging after logger is created
try:
    logger.info(f"Logging configured successfully: level={app_config.logging.level}, file={app_config.logging.file}")
    logger.debug("Debug logging is working!")
except NameError:
    logger.info("Logging configured with fallback settings")

app = FastAPI(title="Grid Trading Backtester")

# Mount static files and templates
ui_dir = Path(__file__).parent.parent / "ui"
templates = Jinja2Templates(directory=ui_dir / "templates")

# Include API routers
app.include_router(backtest.router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})