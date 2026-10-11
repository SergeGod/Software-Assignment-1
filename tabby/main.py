"""Builds the FastAPI application."""

from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tabby.accounts.routes import router as accounts_router
from tabby.config import Settings
from tabby.db import connect, init_db
from tabby.errors import TabbyError
from tabby.ledger.routes import categories_router
from tabby.ledger.routes import router as ledger_router
from tabby.ledger.seed import seed_categories
from tabby.settlement.routes import router as settlement_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)
    with closing(connect(settings.db_path)) as conn:
        seed_categories(conn)

    app = FastAPI(title="Tabby", description="Split shared expenses and settle up.")
    app.state.settings = settings

    @app.exception_handler(TabbyError)
    def handle_tabby_error(request: Request, exc: TabbyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    app.include_router(accounts_router)
    app.include_router(ledger_router)
    app.include_router(categories_router)
    app.include_router(settlement_router)
    return app
