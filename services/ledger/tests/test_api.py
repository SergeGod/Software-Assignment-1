"""The ledger HTTP API end to end, including the endpoint settlement calls."""

import pytest
from fastapi.testclient import TestClient

from tabby.config import Settings
from tabby.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(port=8000, data_dir=tmp_path)))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "ledger"}


def test_api_requires_a_session(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/groups/1/ledger").status_code == 401


def test_sign_up_then_read_the_group_ledger(client):
    body = {"username": "alice", "display_name": "Alice", "password": "secret123"}
    alice = client.post("/api/signup", json=body).json()["id"]  # also sets the session cookie
    group = client.post("/api/groups", json={"name": "Flat"}).json()["id"]
    expense = {
        "description": "Rent",
        "amount_cents": 1000,
        "payer_id": alice,
        "split_type": "equal",
        "category_id": 1,
        "participants": [{"user_id": alice}],
    }
    assert client.post(f"/api/groups/{group}/expenses", json=expense).status_code == 201

    ledger = client.get(f"/api/groups/{group}/ledger").json()
    assert ledger["member_ids"] == [alice]
    assert ledger["expenses"][0]["shares"] == {str(alice): 1000}
    assert client.get("/api/groups/999/ledger").status_code == 404
