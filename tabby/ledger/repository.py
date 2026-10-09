"""All SQL for the ledger domain."""

import sqlite3


def insert_group(conn: sqlite3.Connection, name: str) -> int:
    return conn.execute("INSERT INTO expense_groups (name) VALUES (?)", (name,)).lastrowid


def get_group(conn: sqlite3.Connection, group_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name, created_at FROM expense_groups WHERE id = ?", (group_id,)
    ).fetchone()


def list_groups_for_user(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT g.id, g.name, g.created_at FROM expense_groups g "
        "JOIN group_members m ON m.group_id = g.id WHERE m.user_id = ? ORDER BY g.id DESC",
        (user_id,),
    ).fetchall()


def insert_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> None:
    conn.execute(
        "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (group_id, user_id)
    )


def delete_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> None:
    """Raises sqlite3.IntegrityError if the member is used by any expense."""
    conn.execute(
        "DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id)
    )


def list_member_ids(conn: sqlite3.Connection, group_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT user_id FROM group_members WHERE group_id = ? ORDER BY user_id", (group_id,)
    ).fetchall()
    return [row["user_id"] for row in rows]


def is_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id)
    ).fetchone()
    return row is not None


def insert_expense(
    conn: sqlite3.Connection,
    group_id: int,
    payer_id: int,
    description: str,
    amount_cents: int,
    split_type: str,
    shares: dict[int, int],
) -> int:
    expense_id = conn.execute(
        "INSERT INTO expenses (group_id, payer_id, description, amount_cents, split_type) "
        "VALUES (?, ?, ?, ?, ?)",
        (group_id, payer_id, description, amount_cents, split_type),
    ).lastrowid
    conn.executemany(
        "INSERT INTO expense_shares (expense_id, group_id, user_id, share_cents) "
        "VALUES (?, ?, ?, ?)",
        [(expense_id, group_id, uid, cents) for uid, cents in shares.items()],
    )
    return expense_id


def list_expenses(conn: sqlite3.Connection, group_id: int) -> list[dict]:
    """Expenses of a group, newest first, each with a {user_id: share_cents} dict."""
    expenses = [
        dict(row) | {"shares": {}}
        for row in conn.execute(
            "SELECT id, payer_id, description, amount_cents, split_type, created_at "
            "FROM expenses WHERE group_id = ? ORDER BY id DESC",
            (group_id,),
        )
    ]
    by_id = {expense["id"]: expense for expense in expenses}
    for row in conn.execute(
        "SELECT expense_id, user_id, share_cents FROM expense_shares WHERE group_id = ?",
        (group_id,),
    ):
        by_id[row["expense_id"]]["shares"][row["user_id"]] = row["share_cents"]
    return expenses


def delete_expense(conn: sqlite3.Connection, group_id: int, expense_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM expenses WHERE id = ? AND group_id = ?", (expense_id, group_id)
    )
    return cur.rowcount > 0
