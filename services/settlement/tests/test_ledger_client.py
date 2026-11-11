"""The ledger client against a fake ledger service (no network)."""

import httpx
import pytest

from tabby.errors import Forbidden, NotFound, Unauthorized
from tabby.ledger_client import SESSION_COOKIE, LedgerClient, LedgerExpense, LedgerUnavailable


def client_for(handler) -> LedgerClient:
    return LedgerClient("http://ledger", transport=httpx.MockTransport(handler))


def test_group_ledger_is_parsed_and_the_session_cookie_is_forwarded():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/groups/7/ledger"
        assert request.headers["cookie"] == f"{SESSION_COOKIE}=tok"
        expense = {"id": 1, "payer_id": 1, "amount_cents": 500, "shares": {"1": 250, "2": 250}}
        return httpx.Response(200, json={"group_id": 7, "member_ids": [1, 2], "expenses": [expense]})

    ledger = client_for(handler).get_group_ledger("tok", 7)
    assert ledger.member_ids == [1, 2]
    assert ledger.expenses == [LedgerExpense(1, 1, 500, {1: 250, 2: 250})]


def test_current_user():
    user = {"id": 3, "username": "carol", "display_name": "Carol"}
    assert client_for(lambda r: httpx.Response(200, json=user)).current_user("tok") == user


@pytest.mark.parametrize(
    "status, error",
    [(401, Unauthorized), (403, Forbidden), (404, NotFound), (500, LedgerUnavailable)],
)
def test_ledger_errors_become_tabby_errors(status, error):
    with pytest.raises(error):
        client_for(lambda r: httpx.Response(status)).get_group_ledger("tok", 7)


def test_unreachable_ledger_is_a_503():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LedgerUnavailable) as raised:
        client_for(handler).current_user("tok")
    assert raised.value.status_code == 503
