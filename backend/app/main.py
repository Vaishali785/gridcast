"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import GridCastError
from app.services.ingest import refresh_data
from app.services.repository import Repository
from app.services.store import DataStore

log = logging.getLogger("gridcast")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = DataStore(settings.database_path)
    app.state.repo = Repository(store)
    if store.is_empty() and settings.auto_refresh_on_empty:
        try:
            refresh_data(settings, store)
            log.info("Initial data load complete (%s).", settings.data_source)
        except GridCastError as exc:  # do not crash the API; the UI shows an empty state
            log.error("Initial data load failed: %s %s", exc.message, exc.details)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="GridCast API", version="1.0.0", lifespan=lifespan,
                  description="UK wind forecast vs actual analytics on Elexon BMRS data (WINDFOR / FUELHH).")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.exception_handler(GridCastError)
    async def _app_error(_: Request, exc: GridCastError):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "invalid_request", "message": "Request validation failed",
            "details": {"errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}}})

    app.include_router(router)
    return app


app = create_app()
