"""Business rules for settling up. Reads the ledger only through its interface."""

import sqlite3
from dataclasses import asdict

from tabby.errors import Forbidden, InvalidInput, NotFound
from tabby.ledger import interface as ledger
from tabby.settlement import repository
from tabby.settlement.engine import Payment, net_balances, settle_up


def _ledger_for_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> ledger.GroupLedger:
    group_ledger = ledger.get_group_ledger(conn, group_id)
    if group_ledger is None:
        raise NotFound("group not found")
    if user_id not in group_ledger.member_ids:
        raise Forbidden("you are not a member of this group")
    return group_ledger


def _payments(conn: sqlite3.Connection, group_id: int) -> list[Payment]:
    return [
        Payment(row["from_user_id"], row["to_user_id"], row["amount_cents"])
        for row in repository.list_payments(conn, group_id)
    ]


def get_settlement(conn: sqlite3.Connection, group_id: int, user_id: int) -> dict:
    """Everyone's balance plus the transfers that would settle the group."""
    group_ledger = _ledger_for_member(conn, group_id, user_id)
    balances = net_balances(
        group_ledger.member_ids, group_ledger.expenses, _payments(conn, group_id)
    )
    return {
        "balances": [
            {"user_id": uid, "balance_cents": cents} for uid, cents in sorted(balances.items())
        ],
        "transfers": [asdict(t) for t in settle_up(balances)],
    }


def record_payment(
    conn: sqlite3.Connection, group_id: int, user_id: int, to_user_id: int, amount_cents: int
) -> dict:
    """The logged-in user records that they paid to_user_id back."""
    group_ledger = _ledger_for_member(conn, group_id, user_id)
    if to_user_id == user_id:
        raise InvalidInput("you cannot pay yourself")
    if to_user_id not in group_ledger.member_ids:
        raise InvalidInput("you can only pay a member of this group")
    if amount_cents <= 0:
        raise InvalidInput("amount must be positive")
    with conn:
        payment_id = repository.insert_payment(conn, group_id, user_id, to_user_id, amount_cents)
    return next(p for p in list_payments(conn, group_id, user_id) if p["id"] == payment_id)


def list_payments(conn: sqlite3.Connection, group_id: int, user_id: int) -> list[dict]:
    _ledger_for_member(conn, group_id, user_id)
    return [dict(row) for row in repository.list_payments(conn, group_id)]
