import pytest

from tabby.errors import Forbidden, InvalidInput, NotFound
from tabby.ledger import service as ledger
from tabby.settlement import service

DINNER = 5


@pytest.fixture
def trip(conn, users):
    """alice paid 90 for all three; bob paid 30 just for carol."""
    alice, bob, carol = users["alice"], users["bob"], users["carol"]
    group_id = ledger.create_group(conn, alice, "Trip", [bob, carol])["id"]
    ledger.add_expense(
        conn, group_id, alice, "Dinner", 9000, alice, "equal", DINNER,
        [(alice, 1), (bob, 1), (carol, 1)],
    )
    ledger.add_expense(conn, group_id, bob, "Taxi", 3000, bob, "exact", DINNER, [(carol, 3000)])
    return group_id


def test_settlement_balances_and_transfers(conn, users, trip):
    result = service.get_settlement(conn, trip, users["bob"])
    assert result["balances"] == [
        {"user_id": users["alice"], "balance_cents": 6000},
        {"user_id": users["bob"], "balance_cents": 0},
        {"user_id": users["carol"], "balance_cents": -6000},
    ]
    assert result["transfers"] == [
        {"from_user_id": users["carol"], "to_user_id": users["alice"], "amount_cents": 6000}
    ]


def test_recording_the_suggested_payment_settles_the_group(conn, users, trip):
    payment = service.record_payment(conn, trip, users["carol"], users["alice"], 6000)
    assert payment["from_user_id"] == users["carol"]
    result = service.get_settlement(conn, trip, users["alice"])
    assert all(b["balance_cents"] == 0 for b in result["balances"])
    assert result["transfers"] == []
    assert [p["id"] for p in service.list_payments(conn, trip, users["bob"])] == [payment["id"]]


@pytest.mark.parametrize("to_user, amount", [("carol", 100), ("dave", 100), ("alice", 0)])
def test_record_payment_rejects_invalid_payments(conn, users, trip, to_user, amount):
    with pytest.raises(InvalidInput):
        service.record_payment(conn, trip, users["carol"], users[to_user], amount)


def test_outsiders_cannot_see_or_pay(conn, users, trip):
    with pytest.raises(Forbidden):
        service.get_settlement(conn, trip, users["dave"])
    with pytest.raises(Forbidden):
        service.record_payment(conn, trip, users["dave"], users["alice"], 100)
    with pytest.raises(NotFound):
        service.list_payments(conn, 999, users["alice"])
