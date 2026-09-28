"""FastAPI application: the API under /api plus the built frontend, on 127.0.0.1 only.

Started by scripts/start.py with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db
from app.actions import jobs as job_actions
from app.config import AppConfig, load_config
from app.routers import (
    draft,
    engagements,
    jobs,
    readiness,
    redaction,
    review,
    settings,
    sources,
    system,
    versions,
)
from app.routers.http import ApiError, err_response, error_response
from app.worker import JobWorker

NOT_BUILT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Process Map Studio</title></head>
<body><h1>Process Map Studio</h1>
<p>The app's screens have not been built yet. Run Setup first
(double-click Setup.command on a Mac or setup.bat on Windows), then start the app again.</p>
</body></html>"""


# The anthropic SDK logs whole requests (the source text sent to Claude) at DEBUG, and httpx2
# logs every request at INFO. Transcripts and documents must never reach a log file, so these
# loggers stay at WARNING whatever the rest of the logging is set to.
QUIET_LOGGERS = ("anthropic", "httpx2", "httpcore")


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or load_config()
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    app = FastAPI(title="Process Map Studio", version=config.app_version)
    app.state.config = config
    app.state.sessions = sessions = _open_database(config)
    app.state.worker = worker = JobWorker(
        lambda job_id: job_actions.run_job(config, sessions, job_id)
    )
    job_actions.resume_jobs(sessions, worker.submit)

    app.include_router(system.router)
    app.include_router(settings.router)
    app.include_router(engagements.router)
    app.include_router(sources.router)
    app.include_router(readiness.router)
    app.include_router(jobs.router)
    app.include_router(redaction.router)
    app.include_router(draft.router)
    app.include_router(versions.router)
    app.include_router(review.router)
    _add_request_ids(app)
    _add_error_handlers(app)
    _add_frontend(app, config.frontend_dist)
    return app


def _open_database(config: AppConfig) -> sessionmaker[Session]:
    """Open data/app.db. A brand-new install gets its tables here; an existing database is only
    ever updated by Start (scripts/start.py), which backs it up first (PRD §3.1)."""
    path = db.db_path(config.data_dir)
    if not path.exists():
        db.upgrade(path)
    return db.session_factory(db.make_engine(path))


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", ""))


def _add_request_ids(app: FastAPI) -> None:
    """Give every request a short ID, returned in the X-Request-ID header and in error details."""

    @app.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> Response:
        return err_response(exc.err, request_id_of(request))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> Response:
        # Only field names are returned, never the submitted values (they may hold the API key).
        return error_response(
            422,
            "VALIDATION",
            "Some of the information sent was missing or not in the expected form.",
            {"fields": [".".join(str(p) for p in e["loc"]) for e in exc.errors()]},
            request_id_of(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException) -> Response:
        rid = request_id_of(request)
        if exc.status_code == 404:
            return error_response(
                404, "NOT_FOUND", "That address doesn't exist in the app.", None, rid
            )
        if exc.status_code == 405:
            return error_response(
                405, "METHOD_NOT_ALLOWED", "That action isn't available here.", None, rid
            )
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail), None, rid)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> Response:
        return error_response(
            500,
            "INTERNAL",
            "Something went wrong inside the app. Nothing was changed. "
            "Use Copy details and the Bug-fix prompt to report it.",
            {"type": type(exc).__name__},
            request_id_of(request),
        )


def _add_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend; unknown non-API paths get index.html (client-side screens)."""

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unknown_api(request: Request, rest: str) -> Response:
        return error_response(
            404, "NOT_FOUND", "That address doesn't exist in the app.", None, request_id_of(request)
        )

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(NOT_BUILT_PAGE, status_code=503)
        root = dist.resolve()
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
