"""All SQL for the accounts domain."""

from tabby.db import Connection

PUBLIC_COLUMNS = "id, username, display_name"


def insert_user(conn: Connection, username: str, display_name: str, password_hash: str) -> int:
    row = conn.execute(
        "INSERT INTO users (username, display_name, password_hash) OUTPUT INSERTED.id "
        "VALUES (%s, %s, %s)",
        (username, display_name, password_hash),
    ).fetchone()
    return row["id"]


def get_user_by_username(conn: Connection, username: str) -> dict | None:
    return conn.execute(
        f"SELECT {PUBLIC_COLUMNS}, password_hash FROM users WHERE username = %s", (username,)
    ).fetchone()


def get_users_by_ids(conn: Connection, user_ids: list[int]) -> list[dict]:
    placeholders = ", ".join("%s" for _ in user_ids)
    return conn.execute(
        f"SELECT {PUBLIC_COLUMNS} FROM users WHERE id IN ({placeholders}) ORDER BY id",
        user_ids,
    ).fetchall()


def insert_session(conn: Connection, token_hash: str, user_id: int, days: int) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= SYSUTCDATETIME()")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) "
        "VALUES (%s, %s, DATEADD(day, %s, SYSUTCDATETIME()))",
        (token_hash, user_id, days),
    )


def get_session_user(conn: Connection, token_hash: str) -> dict | None:
    return conn.execute(
        "SELECT u.id, u.username, u.display_name "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = %s AND s.expires_at > SYSUTCDATETIME()",
        (token_hash,),
    ).fetchone()


def delete_session(conn: Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))


def insert_friendship(conn: Connection, a: int, b: int) -> None:
    conn.execute(
        "INSERT INTO friendships (user_id, friend_id) VALUES (%s, %s)", (min(a, b), max(a, b))
    )


def friendship_exists(conn: Connection, a: int, b: int) -> bool:
    row = conn.execute(
        "SELECT 1 AS found FROM friendships WHERE user_id = %s AND friend_id = %s",
        (min(a, b), max(a, b)),
    ).fetchone()
    return row is not None


def list_friends(conn: Connection, user_id: int) -> list[dict]:
    return conn.execute(
        "SELECT u.id, u.username, u.display_name FROM friendships f "
        "JOIN users u ON u.id = CASE WHEN f.user_id = %s THEN f.friend_id ELSE f.user_id END "
        "WHERE f.user_id = %s OR f.friend_id = %s ORDER BY u.display_name",
        (user_id, user_id, user_id),
    ).fetchall()
