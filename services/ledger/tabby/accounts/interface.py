"""The only part of the accounts domain other domains may import.

Accounts lives in the ledger service (ADR-6), so these stay function calls.
"""

from fastapi import Depends, Request

from tabby.accounts import service
from tabby.db import Connection, get_conn
from tabby.errors import Unauthorized


def bearer_token(request: Request) -> str | None:
    """The session token from an `Authorization: Bearer <token>` header.

    A header instead of a cookie: the UI (Static Web Apps) and the two services
    (Container Apps) are on different sites, and browsers do not send cookies
    to another site's API (ADR-6).
    """
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def current_user(request: Request, conn: Connection = Depends(get_conn)) -> dict:
    """FastAPI dependency: the logged-in user, or 401 if there is no valid session."""
    token = bearer_token(request)
    user = service.user_for_session(conn, token) if token else None
    if user is None:
        raise Unauthorized("log in first")
    return user


def are_friends(conn: Connection, a: int, b: int) -> bool:
    return service.are_friends(conn, a, b)


def get_users(conn: Connection, user_ids: list[int]) -> list[dict]:
    """Public profiles (id, username, display_name) for the given ids."""
    return service.get_users(conn, user_ids)
