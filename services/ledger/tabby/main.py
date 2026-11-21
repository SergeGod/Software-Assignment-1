"""Builds the FastAPI application of the ledger service (accounts + ledger)."""

import logging
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tabby import db
from tabby.accounts.routes import router as accounts_router
from tabby.config import Settings
from tabby.errors import TabbyError
from tabby.ledger.routes import categories_router
from tabby.ledger.routes import router as ledger_router
from tabby.ledger.seed import seed_categories
from tabby.observability import add_health, add_request_logging

log = logging.getLogger("tabby")


def prepare_database(settings: Settings) -> None:
    """Startup: wait for the database, apply pending migrations, seed categories."""
    with closing(db.connect_with_retry(settings.database_url)) as conn:
        db.migrate(conn)
        inserted = seed_categories(conn)
        log.info("seeded %d categories", inserted)


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # uvicorn runs this before it starts accepting requests.
        prepare_database(settings)
        yield

    app = FastAPI(
        title="Tabby ledger",
        description="Accounts, groups and shared expenses (Domain A).",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "DELETE"],
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
    app.include_router(accounts_router)
    app.include_router(ledger_router)
    app.include_router(categories_router)
    return app
