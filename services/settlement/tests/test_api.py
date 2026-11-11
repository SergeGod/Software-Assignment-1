"""The settlement HTTP API end to end, with the ledger service faked."""

import pytest
from fastapi.testclient import TestClient

from tabby.config import Settings
from tabby.errors import Unauthorized
from tabby.ledger_client import SESSION_COOKIE
from tabby.main import create_app

from .conftest import ALICE, CAROL, TRIP


class FakeLedger:
    def __init__(self, trip):
        self.trip = trip

    def current_user(self, session_token):
        if session_token != "carol-token":
            raise Unauthorized("log in first")
        return {"id": CAROL, "username": "carol", "display_name": "Carol"}

    def get_group_ledger(self, session_token, group_id):
        return self.trip


@pytest.fixture
def client(tmp_path, trip):
    app = create_app(Settings(port=8000, data_dir=tmp_path), ledger=FakeLedger(trip))
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "settlement"}


def test_requests_without_a_session_are_rejected(client):
    assert client.get(f"/api/groups/{TRIP}/settlement").status_code == 401
    client.cookies.set(SESSION_COOKIE, "someone-else")
    assert client.get(f"/api/groups/{TRIP}/settlement").status_code == 401


def test_pay_the_suggested_transfer_over_http(client):
    client.cookies.set(SESSION_COOKIE, "carol-token")
    transfers = client.get(f"/api/groups/{TRIP}/settlement").json()["transfers"]
    assert transfers == [{"from_user_id": CAROL, "to_user_id": ALICE, "amount_cents": 6000}]

    paid = client.post(
        f"/api/groups/{TRIP}/payments", json={"to_user_id": ALICE, "amount_cents": 6000}
    )
    assert paid.status_code == 201
    assert client.get(f"/api/groups/{TRIP}/settlement").json()["transfers"] == []
    assert len(client.get(f"/api/groups/{TRIP}/payments").json()) == 1
