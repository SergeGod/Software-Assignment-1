"""All SQL for the ledger domain."""

from datetime import date

from tabby.db import Connection


def list_categories(conn: Connection) -> list[dict]:
    return conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()


def category_exists(conn: Connection, category_id: int) -> bool:
    row = conn.execute("SELECT 1 AS found FROM categories WHERE id = %s", (category_id,)).fetchone()
    return row is not None


def spending_by_category(conn: Connection, group_id: int) -> list[dict]:
    return conn.execute(
        "SELECT c.id AS category_id, c.name, SUM(e.amount_cents) AS total_cents "
        "FROM expenses e JOIN categories c ON c.id = e.category_id "
        "WHERE e.group_id = %s GROUP BY c.id, c.name ORDER BY total_cents DESC, c.id",
        (group_id,),
    ).fetchall()


def insert_group(conn: Connection, name: str) -> int:
    row = conn.execute(
        "INSERT INTO expense_groups (name) OUTPUT INSERTED.id VALUES (%s)", (name,)
    ).fetchone()
    return row["id"]


def get_group(conn: Connection, group_id: int) -> dict | None:
    return conn.execute(
        "SELECT id, name, created_at FROM expense_groups WHERE id = %s", (group_id,)
    ).fetchone()


def list_groups_for_user(conn: Connection, user_id: int) -> list[dict]:
    return conn.execute(
        "SELECT g.id, g.name, g.created_at FROM expense_groups g "
        "JOIN group_members m ON m.group_id = g.id WHERE m.user_id = %s ORDER BY g.id DESC",
        (user_id,),
    ).fetchall()


def insert_member(conn: Connection, group_id: int, user_id: int) -> None:
    conn.execute(
        "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)", (group_id, user_id)
    )


def delete_member(conn: Connection, group_id: int, user_id: int) -> None:
    """Raises db.IntegrityError if the member is used by any expense."""
    conn.execute(
        "DELETE FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id)
    )


def list_member_ids(conn: Connection, group_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT user_id FROM group_members WHERE group_id = %s ORDER BY user_id", (group_id,)
    ).fetchall()
    return [row["user_id"] for row in rows]


def is_member(conn: Connection, group_id: int, user_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 AS found FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id),
    ).fetchone()
    return row is not None


def insert_expense(
    conn: Connection,
    group_id: int,
    payer_id: int,
    description: str,
    amount_cents: int,
    split_type: str,
    category_id: int,
    shares: dict[int, int],
    spent_on: date | None = None,
) -> int:
    # Without a date the row gets today's (UTC), like the column default.
    expense_id = conn.execute(
        "INSERT INTO expenses "
        "(group_id, payer_id, description, amount_cents, split_type, category_id, spent_on) "
        "OUTPUT INSERTED.id "
        "VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, CAST(SYSUTCDATETIME() AS DATE)))",
        (
            group_id,
            payer_id,
            description,
            amount_cents,
            split_type,
            category_id,
            spent_on.isoformat() if spent_on else None,
        ),
    ).fetchone()["id"]
    conn.executemany(
        "INSERT INTO expense_shares (expense_id, group_id, user_id, share_cents) "
        "VALUES (%s, %s, %s, %s)",
        [(expense_id, group_id, uid, cents) for uid, cents in shares.items()],
    )
    return expense_id


def list_expenses(conn: Connection, group_id: int) -> list[dict]:
    """Expenses of a group, newest first, each with a {user_id: share_cents} dict."""
    expenses = [
        row | {"shares": {}}
        for row in conn.execute(
            "SELECT id, payer_id, description, amount_cents, split_type, category_id, "
            "spent_on, created_at FROM expenses WHERE group_id = %s ORDER BY id DESC",
            (group_id,),
        ).fetchall()
    ]
    by_id = {expense["id"]: expense for expense in expenses}
    for row in conn.execute(
        "SELECT expense_id, user_id, share_cents FROM expense_shares WHERE group_id = %s",
        (group_id,),
    ).fetchall():
        by_id[row["expense_id"]]["shares"][row["user_id"]] = row["share_cents"]
    return expenses


def delete_expense(conn: Connection, group_id: int, expense_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM expenses WHERE id = %s AND group_id = %s", (expense_id, group_id)
    )
    return cur.rowcount > 0
