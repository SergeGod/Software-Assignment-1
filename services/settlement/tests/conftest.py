"""Shared fixtures: a real SQL Server test database emptied before every test,
and a small group ledger as the ledger service would return it.

TEST_DATABASE_URL points at a database the tests may drop and recreate, e.g.
mssql://sa:<password>@localhost:1433/settlement_test. Tests never touch Azure SQL.
"""

import os
from contextlib import closing
from urllib.parse import unquote, urlparse

import pymssql
import pytest

from tabby import db
from tabby.ledger_client import GroupLedger, LedgerExpense

ALICE, BOB, CAROL, DAVE = 1, 2, 3, 4
TRIP = 7


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
    return url


@pytest.fixture
def conn(database_url):
    conn = db.connect(database_url)
    with conn:
        conn.execute("DELETE FROM payments")
    yield conn
    conn.close()


@pytest.fixture
def trip():
    """alice paid 90 for all three; bob paid 30 just for carol. dave is not a member."""
    return GroupLedger(
        group_id=TRIP,
        member_ids=[ALICE, BOB, CAROL],
        expenses=[
            LedgerExpense(2, payer_id=BOB, amount_cents=3000, shares={CAROL: 3000}),
            LedgerExpense(
                1, payer_id=ALICE, amount_cents=9000, shares={ALICE: 3000, BOB: 3000, CAROL: 3000}
            ),
        ],
    )
