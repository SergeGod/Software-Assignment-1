"""HTTP endpoints for the accounts domain."""

import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from tabby.accounts import service
from tabby.accounts.interface import SESSION_COOKIE, current_user
from tabby.accounts.models import FriendIn, LogInIn, SignUpIn, UserOut
from tabby.db import get_conn

router = APIRouter(prefix="/api", tags=["accounts"])


def _log_in_response(response: Response, request: Request, conn, user_id: int) -> None:
    days = request.app.state.settings.session_days
    token = service.start_session(conn, user_id, days)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=days * 24 * 3600, httponly=True, samesite="lax"
    )


@router.post("/signup", status_code=201, response_model=UserOut)
def sign_up(
    body: SignUpIn,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
):
    user = service.sign_up(conn, body.username, body.display_name, body.password)
    _log_in_response(response, request, conn, user["id"])
    return user


@router.post("/login", response_model=UserOut)
def log_in(
    body: LogInIn,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
):
    user = service.log_in(conn, body.username, body.password)
    _log_in_response(response, request, conn, user["id"])
    return user


@router.post("/logout", status_code=204)
def log_out(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.end_session(conn, token)
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)):
    return user


@router.get("/friends", response_model=list[UserOut])
def list_friends(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    return service.list_friends(conn, user["id"])


@router.post("/friends", status_code=201, response_model=UserOut)
def add_friend(
    body: FriendIn,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return service.add_friend(conn, user["id"], body.username)
