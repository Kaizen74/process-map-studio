"""FastAPI application: the API under /api plus the built frontend, on 127.0.0.1 only.

Started by scripts/start.py with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import AppConfig, load_config
from app.routers import system
from app.routers.http import ApiError, err_response, error_response

NOT_BUILT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Process Map Studio</title></head>
<body><h1>Process Map Studio</h1>
<p>The app's screens have not been built yet. Run Setup first
(double-click Setup.command on a Mac or setup.bat on Windows), then start the app again.</p>
</body></html>"""


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or load_config()
    app = FastAPI(title="Process Map Studio", version=config.app_version)
    app.state.config = config

    app.include_router(system.router)
    _add_error_handlers(app)
    _add_frontend(app, config.frontend_dist)
    return app


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> Response:
        return err_response(exc.err)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> Response:
        return error_response(
            422,
            "VALIDATION",
            "Some of the information sent was missing or not in the expected form.",
            {"fields": [".".join(str(p) for p in e["loc"]) for e in exc.errors()]},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return error_response(404, "NOT_FOUND", "That address doesn't exist in the app.")
        if exc.status_code == 405:
            return error_response(405, "METHOD_NOT_ALLOWED", "That action isn't available here.")
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> Response:
        return error_response(
            500,
            "INTERNAL",
            "Something went wrong inside the app. Nothing was changed. "
            "Use Copy details and the Bug-fix prompt to report it.",
            {"type": type(exc).__name__},
        )


def _add_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend; unknown non-API paths get index.html (client-side screens)."""

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unknown_api(rest: str) -> Response:
        return error_response(404, "NOT_FOUND", "That address doesn't exist in the app.")

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
