"""Runtime settings, read only from environment variables."""

import os
from dataclasses import dataclass

# Always bind every interface so the app is reachable from outside a container.
HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_SESSION_DAYS = 30


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int = DEFAULT_PORT
    session_days: int = DEFAULT_SESSION_DAYS
    # Browser origins allowed to call this API (the UI's address), comma-separated.
    cors_origins: tuple[str, ...] = ()
    # The commit the image was built from, baked in by the Dockerfile.
    version: str = "dev"


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set, e.g. mssql://user:password@host:1433/ledger")
    return Settings(
        database_url=database_url,
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
        session_days=int(os.environ.get("SESSION_DAYS", DEFAULT_SESSION_DAYS)),
        cors_origins=tuple(o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()),
        version=os.environ.get("GIT_SHA", "dev"),
    )
