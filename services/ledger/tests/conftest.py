"""Shared fixtures: a fresh SQLite database per test, and a few users."""

import pytest

from tabby.accounts import service as accounts
from tabby.db import connect, init_db
from tabby.ledger.seed import seed_categories


@pytest.fixture
def conn(tmp_path):
    """A new database file in pytest's temp folder, with schema and categories."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = connect(db_path)
    seed_categories(conn)
    yield conn
    conn.close()


@pytest.fixture
def users(conn):
    """alice, bob, carol and dave. alice is friends with bob and carol, not dave."""
    ids = {
        name: accounts.sign_up(conn, name, name.title(), "secret123")["id"]
        for name in ("alice", "bob", "carol", "dave")
    }
    accounts.add_friend(conn, ids["alice"], "bob")
    accounts.add_friend(conn, ids["alice"], "carol")
    return ids
