"""HTTP client for the ledger service: the seam between Domain A and Domain B.

In Assignment 1 this was a function call to tabby.ledger.interface. Now the
ledger is another service, so the same two questions travel over HTTP:
"who is logged in?" and "what is in this group's ledger?". The settlement
service never touches the ledger's database.
"""

from dataclasses import dataclass

import httpx

from tabby.errors import Forbidden, NotFound, TabbyError, Unauthorized

SESSION_COOKIE = "tabby_session"
TIMEOUT_SECONDS = 5.0


class LedgerUnavailable(TabbyError):
    status_code = 503


@dataclass(frozen=True)
class LedgerExpense:
    id: int
    payer_id: int
    amount_cents: int
    shares: dict[int, int]  # user_id -> cents that user owes for this expense


@dataclass(frozen=True)
class GroupLedger:
    group_id: int
    member_ids: list[int]
    expenses: list[LedgerExpense]


class LedgerClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS, transport=transport)

    def _get(self, path: str, session_token: str) -> httpx.Response:
        # The user's own session cookie is forwarded, so the ledger service
        # decides who the caller is and what they may see.
        try:
            response = self._http.get(path, headers={"Cookie": f"{SESSION_COOKIE}={session_token}"})
        except httpx.HTTPError:
            raise LedgerUnavailable("the ledger service is not reachable") from None
        if response.status_code == 401:
            raise Unauthorized("log in first")
        if response.status_code == 403:
            raise Forbidden("you are not a member of this group")
        if response.status_code == 404:
            raise NotFound("group not found")
        if response.status_code != 200:
            raise LedgerUnavailable("the ledger service returned an error")
        return response

    def current_user(self, session_token: str) -> dict:
        return self._get("/api/me", session_token).json()

    def get_group_ledger(self, session_token: str, group_id: int) -> GroupLedger:
        data = self._get(f"/api/groups/{group_id}/ledger", session_token).json()
        return GroupLedger(
            group_id=data["group_id"],
            member_ids=data["member_ids"],
            expenses=[
                LedgerExpense(
                    e["id"],
                    e["payer_id"],
                    e["amount_cents"],
                    # JSON object keys are always strings; turn them back into ids.
                    {int(uid): cents for uid, cents in e["shares"].items()},
                )
                for e in data["expenses"]
            ],
        )
