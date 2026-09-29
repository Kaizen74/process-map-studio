"""FastAPI app: health endpoint, standard error shape, serving the built frontend."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import AppConfig, load_config
from app.domain.result import Err, ErrorKind
from app.main import create_app
from app.routers.http import STATUS_BY_KIND, unwrap


def make_client(dist: Path) -> TestClient:
    config = dataclasses.replace(load_config(), frontend_dist=dist)
    return TestClient(create_app(config), raise_server_exceptions=False)


@pytest.fixture()
def built_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Placeholder page</body></html>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    (tmp_path / "secret.txt").write_text("outside the dist folder")
    return dist


def assert_error_shape(body: dict[str, object], code: str) -> None:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], dict)


def test_health_reports_versions(built_dist: Path) -> None:
    response = make_client(built_dist).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_version": "1.0.0", "prd_version": "1.5"}


def test_unknown_api_path_uses_standard_error_shape(built_dist: Path) -> None:
    client = make_client(built_dist)
    for method in ("get", "post", "delete"):
        response = getattr(client, method)("/api/no-such-thing")
        assert response.status_code == 404
        assert_error_shape(response.json(), "NOT_FOUND")


def test_wrong_method_uses_standard_error_shape(built_dist: Path) -> None:
    response = make_client(built_dist).post("/api/health")
    assert response.status_code in (404, 405)
    assert "error" in response.json()


def test_root_serves_built_placeholder_page(built_dist: Path) -> None:
    response = make_client(built_dist).get("/")
    assert response.status_code == 200
    assert "Placeholder page" in response.text


def test_assets_are_served(built_dist: Path) -> None:
    response = make_client(built_dist).get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_client_side_screens_get_index_html(built_dist: Path) -> None:
    response = make_client(built_dist).get("/engagements/123/review")
    assert response.status_code == 200
    assert "Placeholder page" in response.text


def test_files_outside_dist_are_never_served(built_dist: Path) -> None:
    response = make_client(built_dist).get("/..%2Fsecret.txt")
    assert "outside the dist folder" not in response.text


def test_missing_build_explains_to_run_setup(tmp_path: Path) -> None:
    response = make_client(tmp_path / "not-built").get("/")
    assert response.status_code == 503
    assert "Run Setup first" in response.text


def test_unexpected_error_is_plain_and_hides_internals(built_dist: Path) -> None:
    app = create_app(dataclasses.replace(load_config(), frontend_dist=built_dist))
    boom = APIRouter()

    @boom.get("/api/test-boom")
    def explode() -> None:
        raise RuntimeError("internal detail /secret/path")

    app.router.routes.insert(0, boom.routes[0])
    response = TestClient(app, raise_server_exceptions=False).get("/api/test-boom")
    assert response.status_code == 500
    assert_error_shape(response.json(), "INTERNAL")
    assert len(response.json()["error"]["details"]["request_id"]) == 12
    assert "/secret/path" not in response.text


def test_validation_error_uses_standard_shape(built_dist: Path) -> None:
    app = create_app(dataclasses.replace(load_config(), frontend_dist=built_dist))
    extra = APIRouter()

    @extra.get("/api/test-number")
    def number(n: int) -> int:
        return n

    app.router.routes.insert(0, extra.routes[0])
    response = TestClient(app).get("/api/test-number?n=abc")
    assert response.status_code == 422
    assert_error_shape(response.json(), "VALIDATION")
    assert response.json()["error"]["details"]["fields"] == ["query.n"]


def test_unwrap_raises_api_error_rendered_in_standard_shape(built_dist: Path) -> None:
    app = create_app(dataclasses.replace(load_config(), frontend_dist=built_dist))
    extra = APIRouter()

    @extra.get("/api/test-blocked")
    def blocked() -> None:
        unwrap(Err(ErrorKind.PUBLISH_BLOCKED, "Publishing is blocked.", {"blockers": []}))

    app.router.routes.insert(0, extra.routes[0])
    response = TestClient(app).get("/api/test-blocked")
    assert response.status_code == 409
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 12
    assert response.json() == {
        "error": {
            "code": "PUBLISH_BLOCKED",
            "message": "Publishing is blocked.",
            "details": {"blockers": [], "request_id": request_id},
        }
    }


def test_every_response_has_a_request_id(built_dist: Path) -> None:
    client = make_client(built_dist)
    first = client.get("/api/health").headers["X-Request-ID"]
    second = client.get("/api/health").headers["X-Request-ID"]
    assert first and second and first != second
    missing = client.get("/api/no-such-thing")
    assert missing.json()["error"]["details"]["request_id"] == missing.headers["X-Request-ID"]


def test_every_error_kind_has_an_http_status() -> None:
    assert set(STATUS_BY_KIND) == set(ErrorKind)


def test_config_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = load_config({})
    assert defaults.port == 8000
    assert defaults.data_dir.name == "data"
    assert defaults.mock_claude is False
    custom: AppConfig = load_config(
        {"APP_PORT": "8123", "DATA_DIR": str(tmp_path), "MOCK_CLAUDE": "1"}
    )
    assert custom.port == 8123
    assert custom.data_dir == tmp_path.resolve()
    assert custom.mock_claude is True


def test_source_text_never_reaches_the_log_even_at_debug_level(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The SDK logs whole requests at DEBUG; the app keeps its loggers at WARNING (privacy)."""
    import json

    from app.services import ai_service
    from tests.services.test_call_claude import GOOD, FakeAnthropic, connect, stage, stream

    create_app(load_config({"PMS_ENV_FILE": str(tmp_path / ".env"), "DATA_DIR": str(tmp_path)}))
    caplog.set_level(logging.DEBUG)
    ai_service.call_claude(connect(FakeAnthropic(stream(json.dumps(GOOD)))), stage())
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "§3.1" not in logged and "Use only the supplied segments" not in logged
