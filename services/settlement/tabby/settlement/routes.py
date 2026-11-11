"""HTTP endpoints for the settlement domain."""

import sqlite3

from fastapi import APIRouter, Depends, Request

from tabby.db import get_conn
from tabby.errors import Unauthorized
from tabby.ledger_client import SESSION_COOKIE, GroupLedger, LedgerClient
from tabby.settlement import service
from tabby.settlement.models import PaymentIn, PaymentOut, SettlementOut

router = APIRouter(prefix="/api/groups", tags=["settlement"])


def session_token(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise Unauthorized("log in first")
    return token


def ledger_client(request: Request) -> LedgerClient:
    return request.app.state.ledger


def current_user(
    token: str = Depends(session_token), ledger: LedgerClient = Depends(ledger_client)
) -> dict:
    """The logged-in user, as the ledger service (which owns accounts) sees them."""
    return ledger.current_user(token)


def group_ledger(
    group_id: int,
    token: str = Depends(session_token),
    ledger: LedgerClient = Depends(ledger_client),
) -> GroupLedger:
    return ledger.get_group_ledger(token, group_id)


@router.get("/{group_id}/settlement", response_model=SettlementOut)
def get_settlement(
    user: dict = Depends(current_user),
    ledger: GroupLedger = Depends(group_ledger),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.get_settlement(conn, ledger, user["id"])


@router.get("/{group_id}/payments", response_model=list[PaymentOut])
def list_payments(
    user: dict = Depends(current_user),
    ledger: GroupLedger = Depends(group_ledger),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.list_payments(conn, ledger, user["id"])


@router.post("/{group_id}/payments", status_code=201, response_model=PaymentOut)
def record_payment(
    body: PaymentIn,
    user: dict = Depends(current_user),
    ledger: GroupLedger = Depends(group_ledger),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.record_payment(conn, ledger, user["id"], body.to_user_id, body.amount_cents)
