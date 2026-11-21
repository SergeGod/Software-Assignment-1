"""Request logging and the /health endpoint, shared shape for both services."""

import logging
import time
from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from tabby import db

log = logging.getLogger("tabby.http")


class HealthOut(BaseModel):
    status: str  # "ok" or "unavailable"
    db: str  # "ok" or "unreachable"
    version: str  # git commit the image was built from


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True
    )


def add_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "%s %s %d %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response


def add_health(app: FastAPI) -> None:
    @app.get(
        "/health",
        response_model=HealthOut,
        tags=["operations"],
        responses={503: {"model": HealthOut, "description": "The service cannot use its database"}},
    )
    def health(request: Request):
        """200 when this service can write and read its own database, 503 otherwise.

        Only this service's own state counts: the other service being down does
        not make this one unhealthy.
        """
        settings = request.app.state.settings
        try:
            with closing(db.connect(settings.database_url)) as conn:
                db.check_read_write(conn)
        except (db.DatabaseError, RuntimeError) as error:
            log.warning("health check failed: %s", error)
            body = {"status": "unavailable", "db": "unreachable", "version": settings.version}
            return JSONResponse(body, status_code=503)
        return {"status": "ok", "db": "ok", "version": settings.version}
