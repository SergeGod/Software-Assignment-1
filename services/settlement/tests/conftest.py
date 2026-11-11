"""Shared fixtures: a fresh settlement database and a small ledger per test."""

import pytest

from tabby.db import connect, init_db
from tabby.ledger_client import GroupLedger, LedgerExpense

ALICE, BOB, CAROL, DAVE = 1, 2, 3, 4
TRIP = 7


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = connect(db_path)
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
