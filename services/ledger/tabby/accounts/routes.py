"""HTTP endpoints for the accounts domain."""

from fastapi import APIRouter, Depends, Request

from tabby.accounts import service
from tabby.accounts.interface import bearer_token, current_user
from tabby.accounts.models import FriendIn, LogInIn, SessionOut, SignUpIn, UserOut
from tabby.db import Connection, get_conn
from tabby.errors import error_responses

router = APIRouter(prefix="/api", tags=["accounts"], responses=error_responses(400, 401, 503))


def _session(request: Request, conn: Connection, user: dict) -> dict:
    token = service.start_session(conn, user["id"], request.app.state.settings.session_days)
    return {"token": token, "user": user}


@router.post("/signup", status_code=201, response_model=SessionOut, responses=error_responses(409))
def sign_up(body: SignUpIn, request: Request, conn: Connection = Depends(get_conn)):
    user = service.sign_up(conn, body.username, body.display_name, body.password)
    return _session(request, conn, user)


@router.post("/login", response_model=SessionOut)
def log_in(body: LogInIn, request: Request, conn: Connection = Depends(get_conn)):
    user = service.log_in(conn, body.username, body.password)
    return _session(request, conn, user)


@router.post("/logout", status_code=204)
def log_out(request: Request, conn: Connection = Depends(get_conn)):
    token = bearer_token(request)
    if token:
        service.end_session(conn, token)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)):
    return user


@router.get("/friends", response_model=list[UserOut])
def list_friends(user: dict = Depends(current_user), conn: Connection = Depends(get_conn)):
    return service.list_friends(conn, user["id"])


@router.post(
    "/friends", status_code=201, response_model=UserOut, responses=error_responses(404, 409)
)
def add_friend(
    body: FriendIn, user: dict = Depends(current_user), conn: Connection = Depends(get_conn)
):
    return service.add_friend(conn, user["id"], body.username)
