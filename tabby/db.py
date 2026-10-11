"""SQLite connection handling and first-boot schema creation."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

PACKAGE_DIR = Path(__file__).resolve().parent
# Each domain owns its own tables. All of them live in the one SQLite file.
SCHEMA_FILES = [
    PACKAGE_DIR / "accounts" / "schema.sql",
    PACKAGE_DIR / "ledger" / "schema.sql",
    PACKAGE_DIR / "settlement" / "schema.sql",
]


def connect(db_path: Path) -> sqlite3.Connection:
    # FastAPI may open the connection and run the endpoint on different worker
    # threads. Each connection still belongs to exactly one request.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite leaves this off by default
    return conn


def init_db(db_path: Path) -> None:
    """Create the data directory, the database file and any missing tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        for schema_file in SCHEMA_FILES:
            conn.executescript(schema_file.read_text())
        conn.commit()
    finally:
        conn.close()


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, always closed afterwards."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
