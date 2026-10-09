"""The only part of the ledger domain other domains may import.

This is the seam between the ledger (Domain A) and settlement (Domain B).
In Assignment 2 get_group_ledger() becomes GET /groups/{id}/ledger on the
ledger service, and nothing on the settlement side has to change.
"""

import sqlite3
from dataclasses import dataclass

from tabby.ledger import repository


@dataclass(frozen=True)
class LedgerExpense:
    id: int
    payer_id: int
    amount_cents: int
    shares: dict[int, int]  # user_id -> cents that user owes for this expense


@dataclass(frozen=True)
class GroupLedger:
    group_id: int
    member_ids: list[int]
    expenses: list[LedgerExpense]


def is_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> bool:
    return repository.is_member(conn, group_id, user_id)


def get_group_ledger(conn: sqlite3.Connection, group_id: int) -> GroupLedger | None:
    """Plain data: who is in the group, who paid what, and who owes what."""
    if repository.get_group(conn, group_id) is None:
        return None
    return GroupLedger(
        group_id=group_id,
        member_ids=repository.list_member_ids(conn, group_id),
        expenses=[
            LedgerExpense(e["id"], e["payer_id"], e["amount_cents"], e["shares"])
            for e in repository.list_expenses(conn, group_id)
        ],
    )
