"""The migration runner, the seed and the settings, against the real test database."""

from datetime import date

import pytest

from tabby import db
from tabby.accounts import service as accounts
from tabby.config import load_settings
from tabby.ledger.seed import SEED_FILE, seed_categories


def count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def test_migrations_are_recorded_and_a_second_run_applies_nothing(conn):
    accounts.sign_up(conn, "alice", "Alice", "secret123")
    applied = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert "001_init.sql" in applied

    assert db.migrate(conn) == []  # second boot
    assert count(conn, "users") == 1  # and the data is still there


@pytest.fixture
def scratch_migrations(conn, tmp_path):
    """A migrations folder with the real files plus test-only ones, cleaned up afterwards."""
    for path in db.MIGRATIONS_DIR.glob("*.sql"):
        (tmp_path / path.name).write_text(path.read_text())
    yield tmp_path
    with conn:
        conn.execute("IF OBJECT_ID('probe', 'U') IS NOT NULL DROP TABLE probe")
        conn.execute("DELETE FROM schema_migrations WHERE version LIKE %s", ("9%",))


def test_a_new_migration_runs_once_with_go_batches(conn, scratch_migrations):
    # The second batch uses the column the first one added: only possible across GO.
    (scratch_migrations / "901_probe.sql").write_text(
        "CREATE TABLE probe (id INT NOT NULL);\nINSERT INTO probe VALUES (1);\nGO\n"
        "ALTER TABLE probe ADD label NVARCHAR(10) NULL;\nGO\n"
        "UPDATE probe SET label = 'backfill';\n"
    )
    assert db.migrate(conn, scratch_migrations) == ["901_probe.sql"]
    assert db.migrate(conn, scratch_migrations) == []
    assert conn.execute("SELECT id, label FROM probe").fetchall() == [{"id": 1, "label": "backfill"}]


def test_a_failing_migration_is_rolled_back_and_not_recorded(conn, scratch_migrations):
    (scratch_migrations / "902_broken.sql").write_text(
        "CREATE TABLE probe (id INT);\nGO\nINSERT INTO no_such_table VALUES (1);\n"
    )
    with pytest.raises(db.DatabaseError):
        db.migrate(conn, scratch_migrations)
    assert conn.execute("SELECT OBJECT_ID('probe', 'U') AS id").fetchone()["id"] is None
    versions = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert "902_broken.sql" not in versions


def test_migration_files_must_be_numbered(conn, tmp_path):
    (tmp_path / "add_stuff.sql").write_text("SELECT 1")
    with pytest.raises(ValueError):
        db.migrate(conn, tmp_path)


def test_health_check_writes_and_reads(conn):
    db.check_read_write(conn)
    with conn:
        conn.execute("DELETE FROM service_heartbeat")
    try:
        with pytest.raises(RuntimeError):
            db.check_read_write(conn)
    finally:
        with conn:
            conn.execute("INSERT INTO service_heartbeat (id) VALUES (1)")


def test_seed_only_loads_into_an_empty_table(conn):
    assert seed_categories(conn) == 0  # seeded at startup already
    assert count(conn, "categories") == 9


@pytest.fixture
def empty_categories(conn):
    with conn:
        conn.execute("DELETE FROM categories")
        conn.execute("DBCC CHECKIDENT ('categories', RESEED, 0)")
    yield
    with conn:  # put the standard categories back with ids 1..9 for the other tests
        conn.execute("DELETE FROM categories")
        conn.execute("DBCC CHECKIDENT ('categories', RESEED, 0)")
    seed_categories(conn, SEED_FILE)


def test_seed_reads_names_from_the_csv_file(conn, tmp_path, empty_categories):
    seed_file = tmp_path / "seed.csv"
    seed_file.write_text("name\nFood\n\nFun\n")
    assert seed_categories(conn, seed_file) == 2
    names = [r["name"] for r in conn.execute("SELECT name FROM categories ORDER BY id")]
    assert names == ["Food", "Fun"]


def test_connect_with_retry_gives_up_on_a_wrong_password(database_url):
    wrong = database_url.replace("@", "x@", 1)
    with pytest.raises(db.DatabaseError):
        db.connect_with_retry(wrong, attempts=2, max_delay=0.1)


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@h:1433/d")
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("SESSION_DAYS", "7")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("GIT_SHA", "abc123")
    s = load_settings()
    assert (s.database_url, s.port, s.session_days, s.version) == ("mssql://u:p@h:1433/d", 9123, 7, "abc123")
    assert s.cors_origins == ("https://a.example", "https://b.example")


def test_settings_defaults_and_required_database_url(monkeypatch):
    for name in ("PORT", "SESSION_DAYS", "CORS_ORIGINS", "GIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@h/d")
    s = load_settings()
    assert (s.port, s.session_days, s.cors_origins, s.version) == (8000, 30, (), "dev")
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError):
        load_settings()


def test_migration_002_adds_spent_on_and_keeps_the_existing_expenses(conn, users):
    """Rewind the schema to migration 001, add an expense the old way, migrate again."""
    alice = users["alice"]
    with conn:
        conn.execute("ALTER TABLE expenses DROP CONSTRAINT df_expenses_spent_on")
        conn.execute("ALTER TABLE expenses DROP COLUMN spent_on")
        conn.execute("DELETE FROM schema_migrations WHERE version = '002_add_expense_spent_on.sql'")
        group_id = conn.execute(
            "INSERT INTO expense_groups (name) OUTPUT INSERTED.id VALUES ('Flat')"
        ).fetchone()["id"]
        conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", (group_id, alice))
        conn.execute(
            "INSERT INTO expenses "
            "(group_id, payer_id, description, amount_cents, split_type, category_id, created_at) "
            "VALUES (%s, %s, 'Old rent', 90000, 'equal', 2, '2026-03-05T23:10:00')",
            (group_id, alice),
        )

    assert db.migrate(conn) == ["002_add_expense_spent_on.sql"]

    rows = conn.execute("SELECT description, amount_cents, spent_on FROM expenses").fetchall()
    assert rows == [{"description": "Old rent", "amount_cents": 90000, "spent_on": date(2026, 3, 5)}]
    assert db.migrate(conn) == []
