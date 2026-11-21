"""Errors the domain services raise. main.py turns them into HTTP responses."""

from pydantic import BaseModel


class TabbyError(Exception):
    status_code = 400


class InvalidInput(TabbyError):
    status_code = 400


class Unauthorized(TabbyError):
    status_code = 401


class Forbidden(TabbyError):
    status_code = 403


class NotFound(TabbyError):
    status_code = 404


class Conflict(TabbyError):
    status_code = 409


class ErrorOut(BaseModel):
    detail: str


_DESCRIPTIONS = {
    400: "Invalid input",
    401: "Missing or expired session token",
    403: "Not a member of this group",
    404: "Not found",
    409: "Conflict with existing data",
    503: "A dependency (database or the other service) is unavailable",
}


def error_responses(*codes: int) -> dict:
    """OpenAPI `responses` for the given error codes, so openapi.json lists them."""
    return {code: {"model": ErrorOut, "description": _DESCRIPTIONS[code]} for code in codes}
