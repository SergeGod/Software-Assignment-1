"""HTTP endpoints for the settlement domain."""

from fastapi import APIRouter, Depends, Request

from tabby.db import Connection, get_conn
from tabby.errors import Unauthorized, error_responses
from tabby.ledger_client import GroupLedger, LedgerClient
from tabby.settlement import service
from tabby.settlement.models import PaymentIn, PaymentOut, SettlementOut

router = APIRouter(
    prefix="/api/groups",
    tags=["settlement"],
    responses=error_responses(400, 401, 403, 404, 503),
)


def bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("log in first")
    return token.strip()


def ledger_client(request: Request) -> LedgerClient:
    return request.app.state.ledger


def group_ledger(
    group_id: int,
    token: str = Depends(bearer_token),
    ledger: LedgerClient = Depends(ledger_client),
) -> GroupLedger:
    """The one call across the seam per request: members, expenses and the caller's id."""
    return ledger.get_group_ledger(token, group_id)


@router.get("/{group_id}/settlement", response_model=SettlementOut)
def get_settlement(
    ledger: GroupLedger = Depends(group_ledger), conn: Connection = Depends(get_conn)
):
    return service.get_settlement(conn, ledger, ledger.viewer_id)


@router.get("/{group_id}/payments", response_model=list[PaymentOut])
def list_payments(
    ledger: GroupLedger = Depends(group_ledger), conn: Connection = Depends(get_conn)
):
    return service.list_payments(conn, ledger, ledger.viewer_id)


@router.post("/{group_id}/payments", status_code=201, response_model=PaymentOut)
def record_payment(
    body: PaymentIn,
    ledger: GroupLedger = Depends(group_ledger),
    conn: Connection = Depends(get_conn),
):
    return service.record_payment(
        conn, ledger, ledger.viewer_id, body.to_user_id, body.amount_cents
    )
