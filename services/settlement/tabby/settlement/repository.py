"""All SQL for the settlement domain."""

import sqlite3


def insert_payment(
    conn: sqlite3.Connection, group_id: int, from_user_id: int, to_user_id: int, amount_cents: int
) -> int:
    return conn.execute(
        "INSERT INTO payments (group_id, from_user_id, to_user_id, amount_cents) "
        "VALUES (?, ?, ?, ?)",
        (group_id, from_user_id, to_user_id, amount_cents),
    ).lastrowid


def list_payments(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, from_user_id, to_user_id, amount_cents, created_at "
        "FROM payments WHERE group_id = ? ORDER BY id DESC",
        (group_id,),
    ).fetchall()
