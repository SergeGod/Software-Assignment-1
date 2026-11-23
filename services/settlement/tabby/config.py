"""Runtime settings, read only from environment variables."""

import os
from dataclasses import dataclass

# Always bind every interface so the app is reachable from outside a container.
HOST = "0.0.0.0"
DEFAULT_PORT = 8000
# Where the ledger service listens. docker compose sets http://ledger:8000.
DEFAULT_LEDGER_URL = "http://localhost:8001"
DEFAULT_LEDGER_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int = DEFAULT_PORT
    ledger_url: str = DEFAULT_LEDGER_URL
    # Every call to the ledger service gives up after this many seconds.
    ledger_timeout_s: float = DEFAULT_LEDGER_TIMEOUT_S
    # Browser origins allowed to call this API (the UI's address), comma-separated.
    cors_origins: tuple[str, ...] = ()
    # The commit the image was built from, baked in by the Dockerfile.
    version: str = "dev"


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set, e.g. mssql://user:password@host:1433/settlement"
        )
    return Settings(
        database_url=database_url,
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
        ledger_url=os.environ.get("LEDGER_URL", DEFAULT_LEDGER_URL).rstrip("/"),
        ledger_timeout_s=float(os.environ.get("LEDGER_TIMEOUT_S", DEFAULT_LEDGER_TIMEOUT_S)),
        cors_origins=tuple(o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()),
        version=os.environ.get("GIT_SHA", "dev"),
    )
