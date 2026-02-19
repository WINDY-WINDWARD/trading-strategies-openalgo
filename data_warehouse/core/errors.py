from __future__ import annotations


class DataWarehouseError(Exception):
    """Base exception for data warehouse failures."""


class RepositoryError(DataWarehouseError):
    """Raised when database operations fail."""


class ProviderError(DataWarehouseError):
    """Raised when provider fetches fail."""
