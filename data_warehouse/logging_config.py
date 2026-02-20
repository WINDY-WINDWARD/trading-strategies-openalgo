"""
Data warehouse logging configuration.

Supports console output and optional rotating file logging.

Environment variables:
- DW_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
- DW_LOG_FILE: Optional log file path. If set, logs are written to this file with rotation.
  Example: DW_LOG_FILE=logs/data_warehouse.log (creates logs/ if needed)
- DW_LOG_MAX_BYTES: Max size per log file before rotation (default: 10MB)
- DW_LOG_BACKUP_COUNT: Number of backup log files to keep (default: 5)
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Setup logging for data warehouse.

    Configures console handler (always) and optional file handler (rotating).
    Creates log directories as needed.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path (e.g., "logs/data_warehouse.log")
        max_bytes: Max size per log file before rotation (10MB default)
        backup_count: Number of backup files to keep (5 default)

    Returns:
        Configured root logger
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format_str)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def configure_from_environment() -> logging.Logger:
    """
    Configure logging from environment variables.

    Reads:
    - DW_LOG_LEVEL (default: INFO)
    - DW_LOG_FILE (optional; if set, enables file logging)
    - DW_LOG_MAX_BYTES (default: 10MB)
    - DW_LOG_BACKUP_COUNT (default: 5)

    Returns:
        Configured root logger
    """
    level = os.getenv("DW_LOG_LEVEL", "INFO")
    log_file = os.getenv("DW_LOG_FILE")
    max_bytes = int(os.getenv("DW_LOG_MAX_BYTES", 10 * 1024 * 1024))
    backup_count = int(os.getenv("DW_LOG_BACKUP_COUNT", 5))

    return setup_logging(
        level=level,
        log_file=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
