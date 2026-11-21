"""Builds the FastAPI application of the settlement service."""

import logging
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tabby import db
from tabby.config import Settings
from tabby.errors import TabbyError
from tabby.ledger_client import LedgerClient
from tabby.observability import add_health, add_request_logging
from tabby.settlement.routes import router as settlement_router

log = logging.getLogger("tabby")


def prepare_database(settings: Settings) -> None:
    """Startup: wait for the database and apply pending migrations."""
    with closing(db.connect_with_retry(settings.database_url)) as conn:
        db.migrate(conn)


def create_app(settings: Settings, ledger: LedgerClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # uvicorn runs this before it starts accepting requests.
        prepare_database(settings)
        yield

    app = FastAPI(
        title="Tabby settlement",
        description="Balances, settle-up plan and payments (Domain B).",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.ledger = ledger or LedgerClient(settings.ledger_url, settings.ledger_timeout_s)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    add_request_logging(app)

    @app.exception_handler(TabbyError)
    def handle_tabby_error(request: Request, exc: TabbyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(db.DatabaseError)
    def handle_database_error(request: Request, exc: db.DatabaseError) -> JSONResponse:
        log.error("database error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse({"detail": "the database is unavailable, try again shortly"}, 503)

    add_health(app)
    app.include_router(settlement_router)
    return app
