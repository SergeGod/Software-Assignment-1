"""Builds the FastAPI application of the ledger service (accounts + ledger)."""

from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tabby.accounts.routes import router as accounts_router
from tabby.config import Settings
from tabby.db import connect, init_db
from tabby.errors import TabbyError
from tabby.ledger.routes import categories_router
from tabby.ledger.routes import router as ledger_router
from tabby.ledger.seed import seed_categories


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)
    with closing(connect(settings.db_path)) as conn:
        seed_categories(conn)

    app = FastAPI(title="Tabby ledger", description="Accounts, groups and shared expenses.")
    app.state.settings = settings

    @app.exception_handler(TabbyError)
    def handle_tabby_error(request: Request, exc: TabbyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "ledger"}

    app.include_router(accounts_router)
    app.include_router(ledger_router)
    app.include_router(categories_router)
    return app
