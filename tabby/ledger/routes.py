"""HTTP endpoints for the ledger domain."""

import sqlite3

from fastapi import APIRouter, Depends

from tabby.accounts.interface import current_user
from tabby.db import get_conn
from tabby.ledger import service
from tabby.ledger.models import (
    CategoryOut,
    ExpenseIn,
    ExpenseOut,
    GroupDetailOut,
    GroupIn,
    GroupOut,
    MemberIn,
    SpendingOut,
)

router = APIRouter(prefix="/api/groups", tags=["ledger"])
categories_router = APIRouter(prefix="/api/categories", tags=["ledger"])


@categories_router.get("", response_model=list[CategoryOut])
def list_categories(
    user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.list_categories(conn)


@router.get("", response_model=list[GroupOut])
def list_groups(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    return service.list_groups(conn, user["id"])


@router.post("", status_code=201, response_model=GroupDetailOut)
def create_group(
    body: GroupIn, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.create_group(conn, user["id"], body.name, body.member_ids)


@router.get("/{group_id}", response_model=GroupDetailOut)
def get_group(
    group_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.get_group(conn, group_id, user["id"])


@router.post("/{group_id}/members", status_code=201, response_model=GroupDetailOut)
def add_member(
    group_id: int,
    body: MemberIn,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.add_member(conn, group_id, user["id"], body.user_id)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: int,
    user_id: int,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    service.remove_member(conn, group_id, user["id"], user_id)


@router.get("/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(
    group_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.list_expenses(conn, group_id, user["id"])


@router.post("/{group_id}/expenses", status_code=201, response_model=ExpenseOut)
def add_expense(
    group_id: int,
    body: ExpenseIn,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.add_expense(
        conn,
        group_id,
        user["id"],
        body.description,
        body.amount_cents,
        body.payer_id,
        body.split_type,
        body.category_id,
        [(p.user_id, p.value) for p in body.participants],
    )


@router.delete("/{group_id}/expenses/{expense_id}", status_code=204)
def delete_expense(
    group_id: int,
    expense_id: int,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    service.delete_expense(conn, group_id, user["id"], expense_id)


@router.get("/{group_id}/spending", response_model=list[SpendingOut])
def spending_by_category(
    group_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)
):
    return service.spending_by_category(conn, group_id, user["id"])
