"""Startup: the lifespan waits for the database, migrates and seeds, idempotently."""

from fastapi.testclient import TestClient

from tabby.config import Settings
from tabby.main import create_app


def test_app_starts_twice_on_the_same_database_without_duplicating_seed(conn, database_url):
    settings = Settings(database_url=database_url)
    for _ in range(2):  # first boot, then a restart
        with TestClient(create_app(settings)) as client:  # `with` runs the lifespan
            assert client.get("/health").status_code == 200

    assert conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"] == 9
    paths = set(create_app(settings).openapi()["paths"])
    assert {"/health", "/api/signup", "/api/groups", "/api/groups/{group_id}/ledger"} <= paths
