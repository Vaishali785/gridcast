"""Structured application errors returned as JSON by the API."""
from __future__ import annotations


class GridCastError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidRequestError(GridCastError):
    status_code = 422
    code = "invalid_request"


class DataNotLoadedError(GridCastError):
    status_code = 409
    code = "data_not_loaded"


class UpstreamError(GridCastError):
    """The Elexon API failed (HTTP error, timeout, rate limit, bad payload)."""

    status_code = 502
    code = "upstream_error"
