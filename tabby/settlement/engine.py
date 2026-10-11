"""Pure settlement logic: net balances and the greedy settle-up plan.

A balance is positive when the group owes that person money, negative when
the person owes the group. All balances in a group always add up to zero.
"""

import heapq
from collections import defaultdict
from dataclasses import dataclass

from tabby.ledger.interface import LedgerExpense


@dataclass(frozen=True)
class Payment:
    from_user_id: int
    to_user_id: int
    amount_cents: int


@dataclass(frozen=True)
class Transfer:
    from_user_id: int
    to_user_id: int
    amount_cents: int


def net_balances(
    member_ids: list[int], expenses: list[LedgerExpense], payments: list[Payment]
) -> dict[int, int]:
    balances: dict[int, int] = defaultdict(int, {uid: 0 for uid in member_ids})
    for expense in expenses:
        balances[expense.payer_id] += expense.amount_cents  # they paid for everyone
        for uid, share in expense.shares.items():
            balances[uid] -= share  # each participant consumed their share
    for payment in payments:
        balances[payment.from_user_id] += payment.amount_cents  # paying back reduces debt
        balances[payment.to_user_id] -= payment.amount_cents  # being paid reduces credit
    return dict(balances)


def settle_up(balances: dict[int, int]) -> list[Transfer]:
    """Greedy plan: the biggest debtor pays the biggest creditor, repeatedly.

    Every transfer brings at least one person to exactly zero, so a group of
    n people never needs more than n - 1 transfers.
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must add up to zero")

    # heapq is a min-heap, so amounts are stored negated to pop the largest
    # first. Equal amounts fall back to the lowest user id: deterministic output.
    debtors = [(balance, uid) for uid, balance in balances.items() if balance < 0]
    creditors = [(-balance, uid) for uid, balance in balances.items() if balance > 0]
    heapq.heapify(debtors)
    heapq.heapify(creditors)

    transfers = []
    while debtors and creditors:
        neg_debt, debtor = heapq.heappop(debtors)
        neg_credit, creditor = heapq.heappop(creditors)
        amount = min(-neg_debt, -neg_credit)
        transfers.append(Transfer(debtor, creditor, amount))
        if -neg_debt > amount:
            heapq.heappush(debtors, (neg_debt + amount, debtor))
        if -neg_credit > amount:
            heapq.heappush(creditors, (neg_credit + amount, creditor))
    return transfers
