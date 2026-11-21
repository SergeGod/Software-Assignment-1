"""Migrations and settings of the settlement service."""

import pytest

from tabby import db
from tabby.config import load_settings


def test_migrations_are_recorded_and_a_second_run_applies_nothing(conn):
    with conn:
        conn.execute(
            "INSERT INTO payments (group_id, from_user_id, to_user_id, amount_cents) "
            "VALUES (1, 1, 2, 500)"
        )
    applied = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert "001_init.sql" in applied
    assert db.migrate(conn) == []
    assert conn.execute("SELECT COUNT(*) AS n FROM payments").fetchone()["n"] == 1


def test_payment_constraints_hold(conn):
    with pytest.raises(db.IntegrityError), conn:
        conn.execute(
            "INSERT INTO payments (group_id, from_user_id, to_user_id, amount_cents) "
            "VALUES (1, 1, 1, 500)"
        )


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@h:1433/d")
    monkeypatch.setenv("LEDGER_URL", "https://ledger.example/")
    monkeypatch.setenv("LEDGER_TIMEOUT_S", "2.5")
    monkeypatch.setenv("CORS_ORIGINS", "https://ui.example")
    monkeypatch.setenv("GIT_SHA", "abc123")
    s = load_settings()
    assert s.ledger_url == "https://ledger.example"
    assert (s.ledger_timeout_s, s.cors_origins, s.version) == (2.5, ("https://ui.example",), "abc123")


def test_settings_defaults_and_required_database_url(monkeypatch):
    for name in ("PORT", "LEDGER_URL", "LEDGER_TIMEOUT_S", "CORS_ORIGINS", "GIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@h/d")
    s = load_settings()
    assert (s.port, s.ledger_url, s.ledger_timeout_s, s.version) == (8000, "http://localhost:8001", 5.0, "dev")
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError):
        load_settings()
