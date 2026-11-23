"""Shared fixtures: a real SQL Server test database, emptied before every test.

TEST_DATABASE_URL points at a database the tests may drop and recreate, using a
login allowed to create databases (sa on the local or CI container), e.g.
mssql://sa:<password>@localhost:1433/ledger_test. Tests never touch Azure SQL.
"""

import os
from contextlib import closing
from urllib.parse import unquote, urlparse

import pymssql
import pytest

from tabby import db
from tabby.accounts import service as accounts
from tabby.ledger.seed import seed_categories

# Deleted before every test, children before parents because of foreign keys.
# categories keeps its seeded rows (ids 1..9), as on a real first boot.
DATA_TABLES = [
    "expense_shares",
    "expenses",
    "group_members",
    "expense_groups",
    "sessions",
    "friendships",
    "users",
]


def recreate_database(database_url: str) -> None:
    """Drop and create the test database, so every run starts from migration 001."""
    url = urlparse(database_url)
    name = url.path.lstrip("/")
    assert name.endswith("_test"), "refusing to drop a database whose name does not end in _test"
    with closing(
        pymssql.connect(
            server=url.hostname,
            port=url.port or 1433,
            user=unquote(url.username),
            password=unquote(url.password),
            database="master",
            autocommit=True,  # CREATE/DROP DATABASE cannot run inside a transaction
        )
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"IF DB_ID('{name}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{name}]; END"
        )
        cursor.execute(f"CREATE DATABASE [{name}]")


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set; see 'Tests and coverage' in the README", 2)
    recreate_database(url)
    with closing(db.connect_with_retry(url, attempts=10)) as conn:
        db.migrate(conn)
        seed_categories(conn)
    return url


@pytest.fixture
def conn(database_url):
    """A connection to the test database with every data table emptied."""
    conn = db.connect(database_url)
    with conn:
        for table in DATA_TABLES:
            conn.execute(f"DELETE FROM {table}")
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
