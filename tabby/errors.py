"""Errors the domain services raise. main.py turns them into HTTP responses."""


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
