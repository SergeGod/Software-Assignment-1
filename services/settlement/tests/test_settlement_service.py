import pytest

from tabby.errors import Forbidden, InvalidInput
from tabby.settlement import service

from .conftest import ALICE, BOB, CAROL, DAVE


def test_settlement_balances_and_transfers(conn, trip):
    result = service.get_settlement(conn, trip, BOB)
    assert result["balances"] == [
        {"user_id": ALICE, "balance_cents": 6000},
        {"user_id": BOB, "balance_cents": 0},
        {"user_id": CAROL, "balance_cents": -6000},
    ]
    assert result["transfers"] == [
        {"from_user_id": CAROL, "to_user_id": ALICE, "amount_cents": 6000}
    ]


def test_recording_the_suggested_payment_settles_the_group(conn, trip):
    payment = service.record_payment(conn, trip, CAROL, ALICE, 6000)
    assert payment["from_user_id"] == CAROL
    result = service.get_settlement(conn, trip, ALICE)
    assert all(b["balance_cents"] == 0 for b in result["balances"])
    assert result["transfers"] == []
    assert [p["id"] for p in service.list_payments(conn, trip, BOB)] == [payment["id"]]


@pytest.mark.parametrize("to_user, amount", [(CAROL, 100), (DAVE, 100), (ALICE, 0)])
def test_record_payment_rejects_invalid_payments(conn, trip, to_user, amount):
    with pytest.raises(InvalidInput):
        service.record_payment(conn, trip, CAROL, to_user, amount)


def test_outsiders_cannot_see_or_pay(conn, trip):
    with pytest.raises(Forbidden):
        service.get_settlement(conn, trip, DAVE)
    with pytest.raises(Forbidden):
        service.record_payment(conn, trip, DAVE, ALICE, 100)
    with pytest.raises(Forbidden):
        service.list_payments(conn, trip, DAVE)
