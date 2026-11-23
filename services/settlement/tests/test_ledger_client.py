"""The ledger client on its own, against fake HTTP responses (no network)."""

import httpx
import pytest

from tabby.errors import Forbidden, NotFound, Unauthorized
from tabby.ledger_client import LedgerClient, LedgerExpense, LedgerUnavailable


def client_for(handler, timeout_s: float = 5.0) -> LedgerClient:
    return LedgerClient("http://ledger", timeout_s, transport=httpx.MockTransport(handler))


def test_group_ledger_is_parsed_and_the_token_is_forwarded():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/groups/7/ledger"
        assert request.headers["authorization"] == "Bearer tok"
        expense = {"id": 1, "payer_id": 1, "amount_cents": 500, "shares": {"1": 250, "2": 250}}
        body = {"group_id": 7, "member_ids": [1, 2], "expenses": [expense], "viewer_id": 2}
        return httpx.Response(200, json=body)

    ledger = client_for(handler).get_group_ledger("tok", 7)
    assert ledger.member_ids == [1, 2]
    assert ledger.viewer_id == 2
    assert ledger.expenses == [LedgerExpense(1, 1, 500, {1: 250, 2: 250})]


def test_every_call_has_a_timeout():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.extensions["timeout"])
        return httpx.Response(404)

    with pytest.raises(NotFound):
        client_for(handler, timeout_s=1.5).get_group_ledger("tok", 7)
    assert seen == {"connect": 1.5, "read": 1.5, "write": 1.5, "pool": 1.5}


@pytest.mark.parametrize(
    "status, error",
    [(401, Unauthorized), (403, Forbidden), (404, NotFound), (500, LedgerUnavailable)],
)
def test_ledger_errors_become_tabby_errors(status, error):
    with pytest.raises(error):
        client_for(lambda r: httpx.Response(status)).get_group_ledger("tok", 7)


@pytest.mark.parametrize("failure", [httpx.ConnectError("refused"), httpx.ConnectTimeout("slow")])
def test_unreachable_or_slow_ledger_is_a_503(failure):
    def handler(request):
        raise failure

    with pytest.raises(LedgerUnavailable) as raised:
        client_for(handler).get_group_ledger("tok", 7)
    assert raised.value.status_code == 503
