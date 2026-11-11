"""Builds the FastAPI application of the settlement service."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tabby.config import Settings
from tabby.db import init_db
from tabby.errors import TabbyError
from tabby.ledger_client import LedgerClient
from tabby.settlement.routes import router as settlement_router


def create_app(settings: Settings, ledger: LedgerClient | None = None) -> FastAPI:
    init_db(settings.db_path)

    app = FastAPI(title="Tabby settlement", description="Balances, settle-up and payments.")
    app.state.settings = settings
    app.state.ledger = ledger or LedgerClient(settings.ledger_url)

    @app.exception_handler(TabbyError)
    def handle_tabby_error(request: Request, exc: TabbyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "settlement"}

    app.include_router(settlement_router)
    return app
