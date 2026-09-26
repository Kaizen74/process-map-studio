"""ai_service Models API calls, run through the real anthropic SDK against a fake network."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from app.config import MOCK_FIXTURES_DIR
from app.domain.models import ModelSummary
from app.domain.result import Err, ErrorKind, Ok
from app.services import ai_service
from app.services.ai_service import AiConnection

KEY = "sk-" + "ant-" + "api03-" + "T" * 40 + "k3y9"
FIXTURE = json.loads((MOCK_FIXTURES_DIR / "models_get" / "default.json").read_text())


def model_json(
    model_id: str = "claude-opus-5-5", *, xhigh: bool = True, pdf: bool = True
) -> dict[str, object]:
    data = json.loads(json.dumps(FIXTURE))
    data["id"] = model_id
    data["display_name"] = model_id
    if not xhigh:
        del data["capabilities"]["effort"]["xhigh"]
    data["capabilities"]["pdf_input"]["supported"] = pdf
    return dict(data)


def error_body(kind: str) -> dict[str, object]:
    return {"type": "error", "error": {"type": kind, "message": "fake"}}


class FakeAnthropic:
    """Records requests and answers with a scripted response."""

    def __init__(self, respond: Callable[[httpx2.Request], httpx2.Response]) -> None:
        self.requests: list[httpx2.Request] = []
        self._respond = respond

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._respond(request)


def connect(
    fake: FakeAnthropic, *, mock: bool = False, fixtures: Path = MOCK_FIXTURES_DIR
) -> AiConnection:
    client = httpx2.Client(transport=httpx2.MockTransport(fake))
    return AiConnection(api_key=KEY, mock=mock, fixtures_dir=fixtures, http_client=client)


def answer(
    status: int, body: object, **headers: str
) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _req: httpx2.Response(
        status, json=body, headers={"retry-after-ms": "1", **headers}
    )


def test_get_model_reads_capabilities_and_sends_the_key_only_as_a_header() -> None:
    fake = FakeAnthropic(answer(200, model_json(xhigh=False)))
    result = ai_service.get_model(connect(fake), "claude-opus-5-5")
    assert result == Ok(
        ModelSummary(
            id="claude-opus-5-5",
            display_name="claude-opus-5-5",
            pdf_input=True,
            structured_outputs=True,
            effort_levels=["low", "medium", "high", "max"],
        )
    )
    request = fake.requests[0]
    assert request.url.path == "/v1/models/claude-opus-5-5"
    assert request.headers["x-api-key"] == KEY
    assert KEY not in str(request.url)


def test_model_without_capabilities_is_reported_conservatively() -> None:
    data = model_json()
    data["capabilities"] = None
    result = ai_service.get_model(connect(FakeAnthropic(answer(200, data))), "x")
    assert isinstance(result, Ok)
    assert result.value.pdf_input is False and result.value.effort_levels == []


@pytest.mark.parametrize(
    ("status", "kind", "error_type", "attempts"),
    [
        (401, ErrorKind.AI_AUTH, "authentication_error", 1),
        (403, ErrorKind.AI_AUTH, "permission_error", 1),
        (404, ErrorKind.NOT_FOUND, "not_found_error", 1),
        (429, ErrorKind.AI_RATE_LIMIT, "rate_limit_error", 2),
        (529, ErrorKind.AI_RATE_LIMIT, "overloaded_error", 2),
        (500, ErrorKind.IO, "api_error", 2),
    ],
)
def test_errors_are_classified_and_only_busy_or_server_errors_retry_once(
    status: int, kind: ErrorKind, error_type: str, attempts: int
) -> None:
    fake = FakeAnthropic(answer(status, error_body(error_type), **{"request-id": "req_123"}))
    result = ai_service.get_model(connect(fake), "claude-opus-5-5")
    assert isinstance(result, Err)
    assert result.kind is kind
    assert result.details["status"] == status
    assert result.details["anthropic_request_id"] == "req_123"
    assert len(fake.requests) == attempts
    assert KEY not in str(result)


def test_no_connection_is_an_io_error() -> None:
    def offline(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("offline", request=request)

    result = ai_service.get_model(connect(FakeAnthropic(offline)), "claude-opus-5-5")
    assert isinstance(result, Err)
    assert result.kind is ErrorKind.IO
    assert result.message == "Anthropic could not be reached."


def test_list_models_follows_every_page() -> None:
    def pages(request: httpx2.Request) -> httpx2.Response:
        if "after_id" not in str(request.url):
            body = {
                "data": [model_json("claude-opus-5-5")],
                "has_more": True,
                "first_id": "claude-opus-5-5",
                "last_id": "claude-opus-5-5",
            }
        else:
            body = {
                "data": [model_json("claude-sonnet-5")],
                "has_more": False,
                "first_id": "claude-sonnet-5",
                "last_id": "claude-sonnet-5",
            }
        return httpx2.Response(200, json=body)

    fake = FakeAnthropic(pages)
    result = ai_service.list_models(connect(fake))
    assert isinstance(result, Ok)
    assert [m.id for m in result.value] == ["claude-opus-5-5", "claude-sonnet-5"]
    assert len(fake.requests) == 2


def test_list_models_classifies_errors() -> None:
    result = ai_service.list_models(
        connect(FakeAnthropic(answer(401, error_body("authentication_error"))))
    )
    assert isinstance(result, Err) and result.kind is ErrorKind.AI_AUTH


def test_the_key_is_never_logged_even_at_debug_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    ai_service.get_model(connect(FakeAnthropic(answer(200, model_json()))), "claude-opus-5-5")
    ai_service.get_model(
        connect(FakeAnthropic(answer(401, error_body("authentication_error")))), "m"
    )
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert caplog.records, "debug logging should have produced records"
    assert KEY not in logged
    assert KEY[-20:] not in logged


def test_connection_repr_hides_the_key() -> None:
    conn = AiConnection(api_key=KEY, mock=True, fixtures_dir=Path("x"))
    assert KEY not in repr(conn) and KEY not in str(conn)


# --- Mock mode (MOCK_CLAUDE=1): no network ------------------------------------------------


def test_mock_mode_uses_fixtures_and_never_calls_the_network() -> None:
    fake = FakeAnthropic(answer(500, {}))
    conn = connect(fake, mock=True)
    got = ai_service.get_model(conn, "claude-opus-5-5")
    listed = ai_service.list_models(conn)
    assert isinstance(got, Ok) and got.value.id == "claude-opus-5-5"
    assert got.value.effort_levels == ["low", "medium", "high", "xhigh", "max"]
    assert isinstance(listed, Ok) and len(listed.value) == 3
    assert fake.requests == []


def test_mock_mode_prefers_a_fixture_named_after_the_model(tmp_path: Path) -> None:
    (tmp_path / "models_get").mkdir()
    (tmp_path / "models_get" / "claude-sonnet-5.json").write_text(
        json.dumps(model_json("claude-sonnet-5", pdf=False))
    )
    (tmp_path / "models_get" / "default.json").write_text(json.dumps(model_json()))
    conn = AiConnection(api_key=KEY, mock=True, fixtures_dir=tmp_path)
    sonnet = ai_service.get_model(conn, "claude-sonnet-5")
    other = ai_service.get_model(conn, "claude-opus-5-5")
    assert isinstance(sonnet, Ok) and sonnet.value.pdf_input is False
    assert isinstance(other, Ok) and other.value.id == "claude-opus-5-5"


def test_mock_mode_missing_or_broken_fixture_is_an_io_error(tmp_path: Path) -> None:
    conn = AiConnection(api_key=KEY, mock=True, fixtures_dir=tmp_path)
    missing = ai_service.list_models(conn)
    assert isinstance(missing, Err) and missing.kind is ErrorKind.IO
    (tmp_path / "models_list").mkdir()
    (tmp_path / "models_list" / "default.json").write_text("{not json")
    broken = ai_service.list_models(conn)
    assert isinstance(broken, Err) and broken.kind is ErrorKind.IO
    missing_get = ai_service.get_model(conn, "x")
    assert isinstance(missing_get, Err) and missing_get.kind is ErrorKind.IO


def test_unexpected_sdk_error_is_an_io_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import anthropic

    def boom(_conn: AiConnection) -> object:
        raise anthropic.AnthropicError("unexpected")

    monkeypatch.setattr(ai_service, "_client", boom)
    result = ai_service.get_model(
        AiConnection(api_key=KEY, mock=False, fixtures_dir=Path(".")), "m"
    )
    assert isinstance(result, Err) and result.kind is ErrorKind.IO
