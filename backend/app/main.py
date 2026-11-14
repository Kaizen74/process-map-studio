"""FastAPI application: the API under /api plus the built frontend, on 127.0.0.1 only.

Started by scripts/start.py with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartParser

from app import db
from app.actions import event_logs as event_log_actions
from app.actions import jobs as job_actions
from app.config import AppConfig, load_config
from app.routers import (
    causes,
    comparisons,
    compass,
    draft,
    engagements,
    event_logs,
    gap,
    images,
    interview,
    jobs,
    leadership,
    publish,
    readiness,
    reality,
    redaction,
    review,
    settings,
    sources,
    system,
    templates,
    value,
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

# The names under which a browser on this computer reaches the app (it listens on 127.0.0.1 only).
# Any other Host means DNS rebinding: a web page whose name was re-pointed at 127.0.0.1, which the
# browser would otherwise treat as that site's own server (deep review, 2026-10-19).
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
FOREIGN_HOST = (
    "This address isn't the app's own, so the app refused the request. "
    "Open the app at http://127.0.0.1:8000."
)
FOREIGN_SITE = "This request came from another website, so the app refused it."
# On every answer: no other site may show the app in a frame (clickjacking: an invisible frame
# whose clicks would come from the app's own origin), no type guessing, no referrer leaving it.
HARDENING = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or load_config()
    # Uploads stay in memory up to the largest size the app accepts, instead of spilling to a
    # temporary file above 1 MB: a system log may carry user IDs, which never touch the disk
    # (constraint 24). Other uploads are smaller still (sources 50 MB).
    MultiPartParser.spool_max_size = max(
        MultiPartParser.spool_max_size, event_log_actions.MAX_BYTES + 1024 * 1024
    )
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
    app.include_router(compass.router)
    app.include_router(comparisons.router)
    app.include_router(sources.router)
    app.include_router(readiness.router)
    app.include_router(jobs.router)
    app.include_router(redaction.router)
    app.include_router(draft.router)
    app.include_router(versions.router)
    app.include_router(review.router)
    app.include_router(publish.router)
    app.include_router(images.router)
    app.include_router(causes.router)
    app.include_router(gap.router)
    app.include_router(leadership.router)
    app.include_router(templates.router)
    app.include_router(interview.router)
    app.include_router(event_logs.router)
    app.include_router(value.router)
    app.include_router(reality.router)
    _add_local_only(app)  # added first, so it runs inside the request ID middleware
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


def _host_and_port(netloc: str, scheme: str) -> tuple[str, str]:
    """("127.0.0.1", "8000") from "127.0.0.1:8000"; the scheme's port when none is given;
    ("", "") for anything that isn't a host."""
    if scheme not in ("http", "https"):
        return "", ""
    parts = urlsplit(f"{scheme}://{netloc}")
    try:
        port = parts.port
    except ValueError:
        return "", ""
    return (parts.hostname or "").lower(), str(port or (443 if scheme == "https" else 80))


def _add_local_only(app: FastAPI) -> None:
    """Answer only requests addressed to the app itself, and accept changes only from the app's
    own pages. Reading needs no origin check: without CORS headers, the browser never lets
    another site read an answer, and a link to a download must keep working."""

    @app.middleware("http")
    async def local_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = _refusal(request) or await call_next(request)
        response.headers.update(HARDENING)
        return response


def _refusal(request: Request) -> Response | None:
    """The 403 for a request the app must not answer; None for one it may."""
    rid = request_id_of(request)
    host = _host_and_port(request.headers.get("host", ""), request.url.scheme)
    if host[0] not in LOCAL_HOSTS:
        return error_response(403, "FOREIGN_HOST", FOREIGN_HOST, None, rid)
    if request.method in SAFE_METHODS:
        return None
    origin = request.headers.get("origin")
    if origin is not None:
        parts = urlsplit(origin)
        came_from = _host_and_port(parts.netloc, parts.scheme)  # "null" → ("", "")
        if came_from[0] not in LOCAL_HOSTS or came_from[1] != host[1]:
            return error_response(403, "FOREIGN_SITE", FOREIGN_SITE, None, rid)
    elif request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return error_response(403, "FOREIGN_SITE", FOREIGN_SITE, None, rid)
    return None


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
