"""All SQL for the settlement domain."""

from tabby.db import Connection


def insert_payment(
    conn: Connection, group_id: int, from_user_id: int, to_user_id: int, amount_cents: int
) -> int:
    row = conn.execute(
        "INSERT INTO payments (group_id, from_user_id, to_user_id, amount_cents) "
        "OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
        (group_id, from_user_id, to_user_id, amount_cents),
    ).fetchone()
    return row["id"]


def list_payments(conn: Connection, group_id: int) -> list[dict]:
    return conn.execute(
        "SELECT id, from_user_id, to_user_id, amount_cents, created_at "
        "FROM payments WHERE group_id = %s ORDER BY id DESC",
        (group_id,),
    ).fetchall()
