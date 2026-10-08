"""Builds the FastAPI application."""

from fastapi import FastAPI

from tabby.config import Settings
from tabby.db import init_db


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)

    app = FastAPI(title="Tabby", description="Split shared expenses and settle up.")
    app.state.settings = settings

    @app.get("/")
    def root() -> dict:
        return {"app": "tabby", "status": "ok"}

    return app
