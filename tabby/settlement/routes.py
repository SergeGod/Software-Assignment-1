"""HTTP endpoints for the settlement domain."""

import sqlite3

from fastapi import APIRouter, Depends

from tabby.accounts.interface import current_user
from tabby.db import get_conn
from tabby.settlement import service
from tabby.settlement.models import PaymentIn, PaymentOut, SettlementOut

router = APIRouter(prefix="/api/groups", tags=["settlement"])


@router.get("/{group_id}/settlement", response_model=SettlementOut)
def get_settlement(
    group_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.get_settlement(conn, group_id, user["id"])


@router.get("/{group_id}/payments", response_model=list[PaymentOut])
def list_payments(
    group_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.list_payments(conn, group_id, user["id"])


@router.post("/{group_id}/payments", status_code=201, response_model=PaymentOut)
def record_payment(
    group_id: int,
    body: PaymentIn,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.record_payment(conn, group_id, user["id"], body.to_user_id, body.amount_cents)
