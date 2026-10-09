"""The only part of the accounts domain other domains may import.

In Assignment 2 each function here becomes a call to the accounts service.
"""

import sqlite3

from fastapi import Depends, Request

from tabby.accounts import service
from tabby.db import get_conn
from tabby.errors import Unauthorized

SESSION_COOKIE = "tabby_session"


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """FastAPI dependency: the logged-in user, or 401 if there is no valid session."""
    token = request.cookies.get(SESSION_COOKIE)
    user = service.user_for_session(conn, token) if token else None
    if user is None:
        raise Unauthorized("log in first")
    return user


def are_friends(conn: sqlite3.Connection, a: int, b: int) -> bool:
    return service.are_friends(conn, a, b)


def get_users(conn: sqlite3.Connection, user_ids: list[int]) -> list[dict]:
    """Public profiles (id, username, display_name) for the given ids."""
    return service.get_users(conn, user_ids)
