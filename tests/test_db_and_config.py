from tabby.accounts import service as accounts
from tabby.config import DEFAULT_DATA_DIR, load_settings
from tabby.db import connect, init_db
from tabby.ledger.seed import seed_categories


def test_init_db_twice_keeps_existing_data(tmp_path):
    db_path = tmp_path / "nested" / "tabby.db"
    init_db(db_path)  # also creates the missing folder
    conn = connect(db_path)
    accounts.sign_up(conn, "alice", "Alice", "secret123")
    conn.close()

    init_db(db_path)  # second boot

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_seed_only_loads_into_an_empty_table(tmp_path):
    db_path = tmp_path / "tabby.db"
    init_db(db_path)
    conn = connect(db_path)
    assert seed_categories(conn) == 9
    assert seed_categories(conn) == 0  # second boot: nothing inserted
    assert conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 9
    conn.close()


def test_seed_reads_names_from_the_csv_file(tmp_path):
    seed_file = tmp_path / "seed.csv"
    seed_file.write_text("name\nFood\n\nFun\n")
    init_db(tmp_path / "tabby.db")
    conn = connect(tmp_path / "tabby.db")
    assert seed_categories(conn, seed_file) == 2
    assert [r["name"] for r in conn.execute("SELECT name FROM categories ORDER BY id")] == [
        "Food",
        "Fun",
    ]
    conn.close()


def test_settings_defaults(monkeypatch):
    for name in ("PORT", "DATA_DIR", "SESSION_DAYS"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.port == 8000
    assert settings.data_dir == DEFAULT_DATA_DIR
    assert settings.session_days == 30
    assert settings.db_path == DEFAULT_DATA_DIR / "tabby.db"


def test_settings_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_DAYS", "7")
    settings = load_settings()
    assert (settings.port, settings.data_dir, settings.session_days) == (9123, tmp_path, 7)
