"""Settings endpoints, and the rule that the API key is never unmasked (PRD constraint 12)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app

KEY = "sk-" + "ant-" + "api03-" + "S3cr3t" * 8 + "Zq9x"


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


def test_get_settings_defaults(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json() == {
        "owner_name": "Owner",
        "model": "claude-opus-5-5",
        "effort": "high",
        "verifier_enabled": True,
        "web_research_enabled": False,
        "key_set": False,
        "key_last4": "",
    }


def test_profile_update_round_trip(client: TestClient) -> None:
    assert client.put("/api/settings/profile", json={"owner_name": "Eric Yim"}).status_code == 200
    assert client.get("/api/settings").json()["owner_name"] == "Eric Yim"


def test_profile_validation_uses_the_standard_shape(client: TestClient) -> None:
    response = client.put("/api/settings/profile", json={"owner_name": ""})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION"
    assert error["message"].startswith("Please enter your name")
    assert error["details"]["field"] == "owner_name"


def test_saved_key_takes_effect_without_restart_and_is_masked(
    client: TestClient, env_file: Path
) -> None:
    response = client.put("/api/settings/key", json={"anthropic_api_key": KEY})
    assert response.status_code == 200
    assert response.json()["key_set"] is True
    assert response.json()["key_last4"] == "Zq9x"
    assert client.get("/api/settings").json()["key_last4"] == "Zq9x"
    assert KEY in env_file.read_text()


def test_the_key_never_appears_in_any_response_or_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    responses = [
        client.put("/api/settings/key", json={"anthropic_api_key": KEY}),
        client.get("/api/settings"),
        # invalid shapes and types: must be refused without echoing the value
        client.put("/api/settings/key", json={"anthropic_api_key": KEY + " extra words"}),
        client.put("/api/settings/key", json={"anthropic_api_key": [KEY]}),
        client.put("/api/settings/key", json={"anthropic_api_key": {"value": KEY}}),
        client.put("/api/settings/key", content=f'{{"anthropic_api_key": "{KEY}"'),
        client.put("/api/settings/profile", json={"owner_name": KEY * 3}),
    ]
    assert [r.status_code for r in responses] == [200, 200, 422, 422, 422, 422, 422]
    for response in responses:
        assert KEY not in response.text
        assert KEY[-12:] not in response.text
        assert all(KEY not in value for value in response.headers.values())
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert KEY not in logged


def test_malformed_key_request_names_the_field_only(client: TestClient) -> None:
    response = client.put("/api/settings/key", json={"anthropic_api_key": 12345})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"] == ["body.anthropic_api_key"]
    assert "12345" not in response.text


def test_unwritable_settings_file_gives_a_plain_error(client: TestClient, env_file: Path) -> None:
    env_file.mkdir()
    response = client.put("/api/settings/profile", json={"owner_name": "Eric"})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "IO"
    assert ".env file in the app folder" in error["message"]
    assert error["details"]["request_id"] == response.headers["X-Request-ID"]


def test_connection_models_and_model_endpoints_in_mock_mode(
    client: TestClient, env_file: Path
) -> None:
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\nMOCK_CLAUDE=1\n")
    tested = client.post("/api/settings/test-connection")
    assert tested.status_code == 200
    assert tested.json()["key_valid"] is True
    assert tested.json()["capabilities"] == {"pdf_input": True, "structured_outputs": True}
    models = client.get("/api/settings/models")
    assert models.status_code == 200 and models.json()["from_anthropic"] is True
    saved = client.put(
        "/api/settings/model",
        json={"model": "claude-sonnet-5", "effort": "medium", "verifier_enabled": False},
    )
    assert saved.status_code == 200
    assert saved.json()["model"] == "claude-sonnet-5"
    for response in (tested, models, saved):
        assert KEY not in response.text


def test_busy_anthropic_is_a_503_in_the_standard_shape(
    client: TestClient, env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.result import Err, ErrorKind

    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    monkeypatch.setattr(
        "app.actions.settings.ai_service.get_model",
        lambda *_: Err(ErrorKind.AI_RATE_LIMIT, "busy", {"status": 429}),
    )
    response = client.post("/api/settings/test-connection")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_RATE_LIMIT"
    assert "try again in a minute" in response.json()["error"]["message"].lower()


def test_model_update_rejects_bad_effort(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model",
        json={"model": "claude-opus-5-5", "effort": "huge", "verifier_enabled": True},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "effort"
