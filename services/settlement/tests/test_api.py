"""Cross-seam integration test: the real settlement app (routes, LedgerClient,
SQL Server) with the ledger service replaced by a stub that speaks HTTP.

The stub answers GET /api/groups/{id}/ledger exactly as the ledger service's
OpenAPI document says, which test_stub_matches_the_ledger_contract checks
against services/ledger/openapi.json. The same flow also runs against the real
two-service compose stack in CI (tests/e2e/cross_seam.py, ADR-9).
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from tabby.config import Settings
from tabby.ledger_client import LedgerClient
from tabby.main import create_app
from tabby.openapi_export import OPENAPI_FILE, render

from .conftest import ALICE, BOB, CAROL, DAVE, TRIP

LEDGER_OPENAPI = Path(__file__).resolve().parents[2] / "ledger" / "openapi.json"
TOKENS = {"alice-token": ALICE, "bob-token": BOB, "carol-token": CAROL, "dave-token": DAVE}
UI_ORIGIN = "https://tabby-ui.example"


def stub_ledger(request: httpx.Request) -> httpx.Response:
    """Plays the ledger service: checks the forwarded token and group membership."""
    assert request.method == "GET"
    user = TOKENS.get(request.headers.get("authorization", "").removeprefix("Bearer "))
    if user is None:
        return httpx.Response(401, json={"detail": "log in first"})
    if request.url.path != f"/api/groups/{TRIP}/ledger":
        return httpx.Response(404, json={"detail": "group not found"})
    if user == DAVE:
        return httpx.Response(403, json={"detail": "you are not a member of this group"})
    return httpx.Response(200, json=ledger_body(user))


def ledger_body(viewer_id: int) -> dict:
    return {
        "group_id": TRIP,
        "member_ids": [ALICE, BOB, CAROL],
        "expenses": [
            {"id": 2, "payer_id": BOB, "amount_cents": 3000, "shares": {str(CAROL): 3000}},
            {
                "id": 1,
                "payer_id": ALICE,
                "amount_cents": 9000,
                "shares": {str(ALICE): 3000, str(BOB): 3000, str(CAROL): 3000},
            },
        ],
        "viewer_id": viewer_id,
    }


def make_client(database_url: str, handler) -> TestClient:
    ledger = LedgerClient("http://ledger", transport=httpx.MockTransport(handler))
    settings = Settings(database_url=database_url, cors_origins=(UI_ORIGIN,))
    return TestClient(create_app(settings, ledger=ledger))


@pytest.fixture
def client(conn, database_url):
    return make_client(database_url, stub_ledger)


def as_user(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_stub_matches_the_ledger_contract():
    """The endpoint settlement calls exists in ledger's OpenAPI with these fields."""
    spec = json.loads(LEDGER_OPENAPI.read_text())
    operation = spec["paths"]["/api/groups/{group_id}/ledger"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    assert set(schema["required"]) == set(ledger_body(ALICE))
    expense_ref = schema["properties"]["expenses"]["items"]["$ref"]
    expense_schema = spec["components"]["schemas"][expense_ref.rsplit("/", 1)[-1]]
    assert set(expense_schema["required"]) == set(ledger_body(ALICE)["expenses"][0])


def test_settle_up_flow_across_the_seam(client):
    settlement = client.get(f"/api/groups/{TRIP}/settlement", headers=as_user("carol-token"))
    assert settlement.status_code == 200
    assert settlement.json()["transfers"] == [
        {"from_user_id": CAROL, "to_user_id": ALICE, "amount_cents": 6000}
    ]

    paid = client.post(
        f"/api/groups/{TRIP}/payments",
        json={"to_user_id": ALICE, "amount_cents": 6000},
        headers=as_user("carol-token"),
    )
    assert paid.status_code == 201
    assert paid.json()["from_user_id"] == CAROL  # the caller, as identified by the ledger

    after = client.get(f"/api/groups/{TRIP}/settlement", headers=as_user("bob-token")).json()
    assert after["transfers"] == []
    assert len(client.get(f"/api/groups/{TRIP}/payments", headers=as_user("bob-token")).json()) == 1


@pytest.mark.parametrize(
    "headers, path, status",
    [
        ({}, f"/api/groups/{TRIP}/settlement", 401),  # no token: rejected before calling ledger
        (as_user("made-up"), f"/api/groups/{TRIP}/settlement", 401),  # ledger says 401
        (as_user("dave-token"), f"/api/groups/{TRIP}/settlement", 403),  # ledger says 403
        (as_user("alice-token"), "/api/groups/99/settlement", 404),  # ledger says 404
    ],
)
def test_ledger_answers_are_passed_on(client, headers, path, status):
    assert client.get(path, headers=headers).status_code == status


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("refused"), httpx.ReadTimeout("too slow")],
    ids=["ledger-down", "ledger-timeout"],
)
def test_partial_failure_is_a_clear_503_and_health_stays_ok(conn, database_url, failure):
    def ledger_down(request):
        raise failure

    client = make_client(database_url, ledger_down)
    response = client.get(f"/api/groups/{TRIP}/settlement", headers=as_user("alice-token"))
    assert response.status_code == 503
    assert "ledger service" in response.json()["detail"]
    # Health is about this service's own database only.
    assert client.get("/health").json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_ledger_5xx_is_a_503(conn, database_url):
    client = make_client(database_url, lambda request: httpx.Response(500))
    response = client.get(f"/api/groups/{TRIP}/payments", headers=as_user("alice-token"))
    assert response.status_code == 503


def test_health_is_503_when_the_database_is_unusable(database_url):
    broken = make_client(database_url.replace("@", "x@", 1), stub_ledger)
    assert broken.get("/health").status_code == 503


def test_cors_allows_only_the_ui_origin(client):
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"}
    path = f"/api/groups/{TRIP}/payments"
    allowed = client.options(path, headers={"Origin": UI_ORIGIN, **preflight})
    assert allowed.headers["access-control-allow-origin"] == UI_ORIGIN
    other = client.options(path, headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in other.headers


def test_every_request_is_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="tabby.http"):
        client.get(f"/api/groups/{TRIP}/settlement", headers=as_user("alice-token"))
    assert any(r.getMessage().startswith(f"GET /api/groups/{TRIP}/settlement 200 ") for r in caplog.records)


def test_app_startup_migrates_idempotently(conn, database_url):
    for _ in range(2):
        with TestClient(create_app(Settings(database_url=database_url))) as client:
            assert client.get("/health").status_code == 200


def test_committed_openapi_file_matches_the_code():
    assert OPENAPI_FILE.read_text() == render(), "run: python -m tabby.openapi_export"
