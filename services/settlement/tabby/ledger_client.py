"""HTTP client for the ledger service: the seam between Domain A and Domain B.

In Assignment 1 this was a function call to tabby.ledger.interface. Now the
ledger is another service, so the question "what is in this group's ledger,
and who is asking?" travels over HTTP. The settlement service never touches
the ledger's database.
"""

from dataclasses import dataclass

import httpx

from tabby.errors import Forbidden, NotFound, TabbyError, Unauthorized


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
    viewer_id: int = 0  # the user the forwarded token belongs to


class LedgerClient:
    def __init__(
        self, base_url: str, timeout_s: float = 5.0, transport: httpx.BaseTransport | None = None
    ):
        self._http = httpx.Client(base_url=base_url, timeout=timeout_s, transport=transport)

    def get_group_ledger(self, token: str, group_id: int) -> GroupLedger:
        """GET /api/groups/{id}/ledger with the user's own bearer token.

        The ledger service owns accounts, so it decides who the caller is and
        whether they belong to the group; its 401/403/404 are passed on as is.
        A timeout, a refused connection or a 5xx becomes a 503 with a clear
        message instead of a hung request or a stack trace.
        """
        try:
            response = self._http.get(
                f"/api/groups/{group_id}/ledger", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.TimeoutException:
            raise LedgerUnavailable(
                "the ledger service did not answer in time, so balances cannot be shown "
                "right now. Try again in a minute."
            ) from None
        except httpx.HTTPError:
            raise LedgerUnavailable(
                "the ledger service is not reachable, so balances cannot be shown right now. "
                "Try again in a minute."
            ) from None
        if response.status_code == 401:
            raise Unauthorized("log in first")
        if response.status_code == 403:
            raise Forbidden("you are not a member of this group")
        if response.status_code == 404:
            raise NotFound("group not found")
        if response.status_code != 200:
            raise LedgerUnavailable("the ledger service returned an error, try again shortly")
        data = response.json()
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
            viewer_id=data["viewer_id"],
        )
