import random

import pytest

from tabby.ledger.interface import LedgerExpense
from tabby.settlement.engine import Payment, Transfer, net_balances, settle_up


def test_net_balances_from_expenses():
    expenses = [LedgerExpense(1, payer_id=1, amount_cents=9000, shares={1: 3000, 2: 3000, 3: 3000})]
    assert net_balances([1, 2, 3], expenses, []) == {1: 6000, 2: -3000, 3: -3000}


def test_members_without_expenses_have_zero_balance():
    assert net_balances([1, 2], [], []) == {1: 0, 2: 0}


def test_payments_reduce_debt_and_credit():
    expenses = [LedgerExpense(1, payer_id=1, amount_cents=2000, shares={1: 1000, 2: 1000})]
    payments = [Payment(from_user_id=2, to_user_id=1, amount_cents=400)]
    assert net_balances([1, 2], expenses, payments) == {1: 600, 2: -600}


def test_payment_by_someone_no_longer_a_member_still_counts():
    payments = [Payment(from_user_id=9, to_user_id=1, amount_cents=100)]
    assert net_balances([1], [], payments) == {1: -100, 9: 100}


def test_settle_up_one_creditor_two_debtors():
    assert settle_up({1: 6000, 2: -3000, 3: -3000}) == [
        Transfer(2, 1, 3000),
        Transfer(3, 1, 3000),
    ]


def test_settle_up_skips_the_middle_of_a_debt_chain():
    # alice owes bob 10, bob owes carol 10: alice can pay carol directly.
    assert settle_up({1: -1000, 2: 0, 3: 1000}) == [Transfer(1, 3, 1000)]


def test_settle_up_biggest_debtor_pays_biggest_creditor_first():
    transfers = settle_up({1: 500, 2: 1500, 3: -1800, 4: -200})
    assert transfers[0] == Transfer(3, 2, 1500)


def test_settled_group_needs_no_transfers():
    assert settle_up({1: 0, 2: 0}) == []
    assert settle_up({}) == []


def test_settle_up_rejects_balances_that_do_not_add_up():
    with pytest.raises(ValueError):
        settle_up({1: 100, 2: -50})


@pytest.mark.parametrize("seed", range(50))
def test_settle_up_settles_everyone_in_at_most_n_minus_1_transfers(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 12)
    balances = {uid: rng.randint(-10_000, 10_000) for uid in range(1, n)}
    balances[n] = -sum(balances.values())

    transfers = settle_up(balances)

    remaining = dict(balances)
    for t in transfers:
        assert t.amount_cents > 0
        remaining[t.from_user_id] += t.amount_cents
        remaining[t.to_user_id] -= t.amount_cents
    assert all(cents == 0 for cents in remaining.values())
    assert len(transfers) <= n - 1
