"""Business rules for settling up.

The group's ledger arrives as plain data (fetched from the ledger service by
the routes); this module only adds the payments it owns itself.
"""

from dataclasses import asdict

from tabby.db import Connection
from tabby.errors import Forbidden, InvalidInput
from tabby.ledger_client import GroupLedger
from tabby.settlement import repository
from tabby.settlement.engine import Payment, net_balances, settle_up


def _require_member(group_ledger: GroupLedger, user_id: int) -> None:
    if user_id not in group_ledger.member_ids:
        raise Forbidden("you are not a member of this group")


def _payments(conn: Connection, group_id: int) -> list[Payment]:
    return [
        Payment(row["from_user_id"], row["to_user_id"], row["amount_cents"])
        for row in repository.list_payments(conn, group_id)
    ]


def get_settlement(conn: Connection, group_ledger: GroupLedger, user_id: int) -> dict:
    """Everyone's balance plus the transfers that would settle the group."""
    _require_member(group_ledger, user_id)
    balances = net_balances(
        group_ledger.member_ids, group_ledger.expenses, _payments(conn, group_ledger.group_id)
    )
    return {
        "balances": [
            {"user_id": uid, "balance_cents": cents} for uid, cents in sorted(balances.items())
        ],
        "transfers": [asdict(t) for t in settle_up(balances)],
    }


def record_payment(
    conn: Connection,
    group_ledger: GroupLedger,
    user_id: int,
    to_user_id: int,
    amount_cents: int,
) -> dict:
    """The logged-in user records that they paid to_user_id back."""
    _require_member(group_ledger, user_id)
    if to_user_id == user_id:
        raise InvalidInput("you cannot pay yourself")
    if to_user_id not in group_ledger.member_ids:
        raise InvalidInput("you can only pay a member of this group")
    if amount_cents <= 0:
        raise InvalidInput("amount must be positive")
    with conn:
        payment_id = repository.insert_payment(
            conn, group_ledger.group_id, user_id, to_user_id, amount_cents
        )
    return next(p for p in list_payments(conn, group_ledger, user_id) if p["id"] == payment_id)


def list_payments(conn: Connection, group_ledger: GroupLedger, user_id: int) -> list[dict]:
    _require_member(group_ledger, user_id)
    return [dict(row) for row in repository.list_payments(conn, group_ledger.group_id)]
