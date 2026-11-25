"""The ledger HTTP API end to end against the test database, including the
endpoint the settlement service calls, /health, CORS and request logs."""

import logging

import pytest
from fastapi.testclient import TestClient

from tabby.config import Settings
from tabby.main import create_app
from tabby.openapi_export import OPENAPI_FILE, render

UI_ORIGIN = "https://tabby-ui.example"


@pytest.fixture
def client(conn, database_url):
    return TestClient(create_app(Settings(database_url=database_url, cors_origins=(UI_ORIGIN,))))


def sign_up(client, username: str) -> dict:
    body = {"username": username, "display_name": username.title(), "password": "secret123"}
    response = client.post("/api/signup", json=body)
    assert response.status_code == 201
    return response.json()


def auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['token']}"}


def test_health_reports_db_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_health_is_503_when_the_database_is_unusable(database_url):
    broken = TestClient(create_app(Settings(database_url=database_url.replace("@", "x@", 1))))
    response = broken.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_api_requires_a_bearer_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/groups/1/ledger").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer made-up"}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_sign_up_log_in_and_log_out_with_tokens(client):
    session = sign_up(client, "alice")
    assert client.get("/api/me", headers=auth(session)).json() == session["user"]

    login = client.post("/api/login", json={"username": "alice", "password": "secret123"}).json()
    assert login["user"] == session["user"] and login["token"] != session["token"]

    assert client.post("/api/logout", headers=auth(login)).status_code == 204
    assert client.get("/api/me", headers=auth(login)).status_code == 401
    assert client.get("/api/me", headers=auth(session)).status_code == 200  # other session lives on


def test_friends_groups_and_the_group_ledger_for_settlement(client):
    alice, bob = sign_up(client, "alice"), sign_up(client, "bob")
    a, b = alice["user"]["id"], bob["user"]["id"]
    assert client.post("/api/friends", json={"username": "bob"}, headers=auth(alice)).status_code == 201
    assert [f["id"] for f in client.get("/api/friends", headers=auth(bob)).json()] == [a]

    group = client.post("/api/groups", json={"name": "Flat", "member_ids": [b]}, headers=auth(alice))
    group_id = group.json()["id"]
    expense = {
        "description": "Rent",
        "amount_cents": 1000,
        "payer_id": a,
        "split_type": "equal",
        "category_id": 1,
        "participants": [{"user_id": a}, {"user_id": b}],
        "spent_on": "2026-01-31",
    }
    created = client.post(f"/api/groups/{group_id}/expenses", json=expense, headers=auth(alice))
    assert created.status_code == 201
    assert created.json()["spent_on"] == "2026-01-31"
    assert len(client.get(f"/api/groups/{group_id}/expenses", headers=auth(bob)).json()) == 1
    assert client.get(f"/api/groups/{group_id}/spending", headers=auth(bob)).json()[0]["total_cents"] == 1000
    assert len(client.get("/api/categories", headers=auth(bob)).json()) == 9

    ledger = client.get(f"/api/groups/{group_id}/ledger", headers=auth(bob)).json()
    assert ledger["member_ids"] == [a, b]
    assert ledger["viewer_id"] == b
    assert ledger["expenses"][0]["shares"] == {str(a): 500, str(b): 500}
    assert client.get("/api/groups/999999/ledger", headers=auth(bob)).status_code == 404

    carol = sign_up(client, "carol")
    assert client.get(f"/api/groups/{group_id}/ledger", headers=auth(carol)).status_code == 403


def test_cors_allows_only_the_ui_origin(client):
    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    allowed = client.options("/api/me", headers={"Origin": UI_ORIGIN, **preflight})
    assert allowed.headers["access-control-allow-origin"] == UI_ORIGIN
    other = client.options("/api/me", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in other.headers


def test_every_request_is_logged_with_method_path_status_and_duration(client, caplog):
    with caplog.at_level(logging.INFO, logger="tabby.http"):
        client.get("/api/me")
    assert any(r.getMessage().startswith("GET /api/me 401 ") for r in caplog.records)


def test_committed_openapi_file_matches_the_code():
    assert OPENAPI_FILE.read_text() == render(), "run: python -m tabby.openapi_export"
