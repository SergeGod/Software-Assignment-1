"""Business rules for accounts: sign-up, login sessions and friendships."""

import re
import sqlite3

from tabby.accounts import repository, security
from tabby.errors import Conflict, InvalidInput, NotFound, Unauthorized

USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,30}$")
MIN_PASSWORD_LENGTH = 8


def normalize_username(username: str) -> str:
    return username.strip().lower()


def _public(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}


def sign_up(conn: sqlite3.Connection, username: str, display_name: str, password: str) -> dict:
    username = normalize_username(username)
    display_name = display_name.strip()
    if not USERNAME_PATTERN.match(username):
        raise InvalidInput("username must be 3-30 characters: letters, digits or _")
    if not display_name:
        raise InvalidInput("display name must not be empty")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInput(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if repository.get_user_by_username(conn, username) is not None:
        raise Conflict("username is already taken")
    with conn:
        user_id = repository.insert_user(
            conn, username, display_name, security.hash_password(password)
        )
    return {"id": user_id, "username": username, "display_name": display_name}


def log_in(conn: sqlite3.Connection, username: str, password: str) -> dict:
    row = repository.get_user_by_username(conn, normalize_username(username))
    # Same message either way, so the response does not reveal which usernames exist.
    if row is None or not security.verify_password(password, row["password_hash"]):
        raise Unauthorized("wrong username or password")
    return _public(row)


def start_session(conn: sqlite3.Connection, user_id: int, days: int) -> str:
    """Create a session and return the raw token. Only its hash is stored."""
    token = security.new_session_token()
    with conn:
        repository.insert_session(conn, security.hash_token(token), user_id, days)
    return token


def end_session(conn: sqlite3.Connection, token: str) -> None:
    with conn:
        repository.delete_session(conn, security.hash_token(token))


def user_for_session(conn: sqlite3.Connection, token: str) -> dict | None:
    row = repository.get_session_user(conn, security.hash_token(token))
    return _public(row) if row else None


def add_friend(conn: sqlite3.Connection, user_id: int, friend_username: str) -> dict:
    row = repository.get_user_by_username(conn, normalize_username(friend_username))
    if row is None:
        raise NotFound("no user with that username")
    if row["id"] == user_id:
        raise InvalidInput("you cannot add yourself as a friend")
    if repository.friendship_exists(conn, user_id, row["id"]):
        raise Conflict("you are already friends")
    with conn:
        repository.insert_friendship(conn, user_id, row["id"])
    return _public(row)


def list_friends(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    return [_public(row) for row in repository.list_friends(conn, user_id)]


def are_friends(conn: sqlite3.Connection, a: int, b: int) -> bool:
    return repository.friendship_exists(conn, a, b)


def get_users(conn: sqlite3.Connection, user_ids: list[int]) -> list[dict]:
    if not user_ids:
        return []
    return [_public(row) for row in repository.get_users_by_ids(conn, user_ids)]
