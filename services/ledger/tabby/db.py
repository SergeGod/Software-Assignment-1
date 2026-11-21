"""SQL Server access: connections from DATABASE_URL, retries, and versioned migrations."""

import logging
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Self
from urllib.parse import unquote, urlparse

import pymssql
from fastapi import Request

log = logging.getLogger("tabby.db")

IntegrityError = pymssql.IntegrityError
DatabaseError = pymssql.Error

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_NAME = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")
# A migration file may hold several batches separated by a line with only GO,
# as in sqlcmd. SQL Server compiles a whole batch before running it, so a
# column added in one batch can only be used in the next one.
GO_LINE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


class Connection:
    """A thin wrapper so repositories keep the shape they had on SQLite:
    conn.execute(sql, params).fetchall() with rows as dicts, and `with conn:`
    as one transaction (commit on success, rollback on error)."""

    def __init__(self, raw: pymssql.Connection):
        self._raw = raw

    def execute(self, sql: str, params: tuple | list = ()) -> pymssql.Cursor:
        cursor = self._raw.cursor(as_dict=True)
        # Without parameters pymssql leaves % signs in the SQL alone.
        cursor.execute(sql, tuple(params) if params else None)
        return cursor

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        self._raw.cursor().executemany(sql, rows)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


def connect(database_url: str, login_timeout: int = 5) -> Connection:
    """DATABASE_URL looks like mssql://user:password@host:1433/database."""
    url = urlparse(database_url)
    raw = pymssql.connect(
        server=url.hostname,
        port=url.port or 1433,
        user=unquote(url.username or ""),
        password=unquote(url.password or ""),
        database=url.path.lstrip("/"),
        login_timeout=login_timeout,
        timeout=30,
        tds_version="7.4",
    )
    return Connection(raw)


def connect_with_retry(database_url: str, attempts: int = 20, max_delay: float = 10.0) -> Connection:
    """Keep trying with exponential backoff: 1, 2, 4, 8, 10, 10... seconds (about 2.5 min).

    Locally SQL Server needs ~20 s after its container starts. On Azure a paused
    serverless database takes up to a minute to resume and refuses logins
    meanwhile (error 40613), so the first start after idle has to wait for it.
    """
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            return connect(database_url)
        except DatabaseError as error:
            if attempt == attempts:
                raise
            log.warning("database not ready (attempt %d/%d): %s", attempt, attempts, error)
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
    raise AssertionError("unreachable")


def migrate(conn: Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every migration file not yet recorded in schema_migrations, in order.

    Each file runs in one transaction together with the row that records it, so
    a failing migration leaves no half-applied schema and is retried on the next
    start. Applied files are never edited; a fix goes in a new file.
    """
    with conn:
        conn.execute(
            "IF OBJECT_ID('schema_migrations', 'U') IS NULL "
            "CREATE TABLE schema_migrations ("
            "  version    NVARCHAR(255) NOT NULL PRIMARY KEY,"
            "  applied_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME())"
        )
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    files = sorted(migrations_dir.glob("*.sql"))
    for path in files:
        if not MIGRATION_NAME.match(path.name):
            raise ValueError(f"migration file name must look like 001_name.sql: {path.name}")
    pending = [path for path in files if path.name not in applied]
    for path in pending:
        log.info("applying migration %s", path.name)
        with conn:
            for batch in GO_LINE.split(path.read_text()):
                if batch.strip():
                    conn.execute(batch)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
    log.info("schema up to date: %d migration(s) applied now, %d in total", len(pending), len(files))
    return [path.name for path in pending]


def check_read_write(conn: Connection) -> None:
    """Used by /health: one write and one read on this service's own database."""
    with conn:
        updated = conn.execute(
            "UPDATE service_heartbeat SET checked_at = SYSUTCDATETIME() WHERE id = 1"
        ).rowcount
        conn.execute("SELECT checked_at FROM service_heartbeat WHERE id = 1").fetchone()
    if updated != 1:
        raise RuntimeError("service_heartbeat row is missing")


def get_conn(request: Request) -> Iterator[Connection]:
    """FastAPI dependency: one connection per request, always closed afterwards."""
    conn = connect(request.app.state.settings.database_url)
    try:
        yield conn
    finally:
        conn.close()
