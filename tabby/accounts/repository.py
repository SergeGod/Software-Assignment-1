"""All SQL for the accounts domain."""

import sqlite3

PUBLIC_COLUMNS = "id, username, display_name"


def insert_user(
    conn: sqlite3.Connection, username: str, display_name: str, password_hash: str
) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
        (username, display_name, password_hash),
    )
    return cur.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {PUBLIC_COLUMNS}, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()


def get_users_by_ids(conn: sqlite3.Connection, user_ids: list[int]) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in user_ids)
    return conn.execute(
        f"SELECT {PUBLIC_COLUMNS} FROM users WHERE id IN ({placeholders}) ORDER BY id",
        user_ids,
    ).fetchall()


def insert_session(conn: sqlite3.Connection, token_hash: str, user_id: int, days: int) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', ?))",
        (token_hash, user_id, f"+{days} days"),
    )


def get_session_user(conn: sqlite3.Connection, token_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT u.id, u.username, u.display_name "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > datetime('now')",
        (token_hash,),
    ).fetchone()


def delete_session(conn: sqlite3.Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def insert_friendship(conn: sqlite3.Connection, a: int, b: int) -> None:
    conn.execute(
        "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (min(a, b), max(a, b))
    )


def friendship_exists(conn: sqlite3.Connection, a: int, b: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?", (min(a, b), max(a, b))
    ).fetchone()
    return row is not None


def list_friends(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT u.id, u.username, u.display_name FROM friendships f "
        "JOIN users u ON u.id = CASE WHEN f.user_id = ? THEN f.friend_id ELSE f.user_id END "
        "WHERE f.user_id = ? OR f.friend_id = ? ORDER BY u.display_name",
        (user_id, user_id, user_id),
    ).fetchall()
