"""Builds the FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tabby.accounts.routes import router as accounts_router
from tabby.config import Settings
from tabby.db import init_db
from tabby.errors import TabbyError


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)

    app = FastAPI(title="Tabby", description="Split shared expenses and settle up.")
    app.state.settings = settings

    @app.exception_handler(TabbyError)
    def handle_tabby_error(request: Request, exc: TabbyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.get("/")
    def root() -> dict:
        return {"app": "tabby", "status": "ok"}

    app.include_router(accounts_router)
    return app
