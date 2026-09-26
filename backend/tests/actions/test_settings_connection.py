"""Settings actions that talk to Anthropic: test connection, model list, model choice."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.actions import settings
from app.config import AppConfig
from app.domain.models import ModelSummary
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services.ai_service import AiConnection

KEY = "sk-" + "ant-" + "api03-" + "C" * 30 + "abcd"

OPUS = ModelSummary(
    id="claude-opus-5-5",
    display_name="Claude Opus 5.5",
    pdf_input=True,
    structured_outputs=True,
    effort_levels=["low", "medium", "high", "xhigh", "max"],
)


@pytest.fixture()
def with_key(env_file: Path) -> None:
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\n")


def fake_get(monkeypatch: pytest.MonkeyPatch, result: Result[ModelSummary]) -> list[str]:
    calls: list[str] = []

    def get_model(conn: AiConnection, model_id: str) -> Result[ModelSummary]:
        assert conn.api_key == KEY
        calls.append(model_id)
        return result

    monkeypatch.setattr("app.actions.settings.ai_service.get_model", get_model)
    return calls


def fake_list(monkeypatch: pytest.MonkeyPatch, result: Result[list[ModelSummary]]) -> None:
    monkeypatch.setattr("app.actions.settings.ai_service.list_models", lambda _conn: result)


def test_no_key_says_so_without_calling_anthropic(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_get(monkeypatch, Ok(OPUS))
    result = settings.test_connection(settings_config)
    assert isinstance(result, Ok)
    assert result.value.key_valid is False and result.value.message == settings.NO_KEY
    assert calls == []


@pytest.mark.usefixtures("with_key")
def test_working_key_and_model(settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_get(monkeypatch, Ok(OPUS))
    result = settings.test_connection(settings_config)
    assert isinstance(result, Ok)
    assert result.value.model_dump() == {
        "key_valid": True,
        "model_available": True,
        "capabilities": {"pdf_input": True, "structured_outputs": True},
        "message": "Connected. Your key works and claude-opus-5-5 is available.",
    }
    assert calls == ["claude-opus-5-5"]


@pytest.mark.usefixtures("with_key")
def test_rejected_key(settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get(monkeypatch, Err(ErrorKind.AI_AUTH, "rejected", {"status": 401}))
    result = settings.test_connection(settings_config)
    assert isinstance(result, Ok)
    assert result.value.key_valid is False
    assert result.value.message == settings.KEY_REJECTED


@pytest.mark.usefixtures("with_key")
def test_model_not_available(settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get(monkeypatch, Err(ErrorKind.NOT_FOUND, "missing", {"status": 404}))
    result = settings.test_connection(settings_config)
    assert isinstance(result, Ok)
    assert (result.value.key_valid, result.value.model_available) == (True, False)
    assert "isn't available to your account" in result.value.message


@pytest.mark.usefixtures("with_key")
@pytest.mark.parametrize(
    ("kind", "message"),
    [(ErrorKind.AI_RATE_LIMIT, settings.BUSY), (ErrorKind.IO, settings.UNREACHABLE)],
)
def test_busy_or_unreachable_are_errors_with_plain_messages(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch, kind: ErrorKind, message: str
) -> None:
    fake_get(monkeypatch, Err(kind, "raw", {"status": 429}))
    result = settings.test_connection(settings_config)
    assert result == Err(kind, message, {"status": 429})


def test_mock_mode_runs_the_whole_path_offline(settings_config: AppConfig, env_file: Path) -> None:
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\nMOCK_CLAUDE=1\n")
    result = settings.test_connection(settings_config)
    assert isinstance(result, Ok) and result.value.model_available is True
    models = settings.list_model_choices(settings_config)
    assert isinstance(models, Ok) and models.value.from_anthropic is True
    assert [m.id for m in models.value.models][:1] == ["claude-opus-5-5"]


def test_model_list_without_key_offers_the_current_model(settings_config: AppConfig) -> None:
    result = settings.list_model_choices(settings_config)
    assert isinstance(result, Ok)
    assert [m.id for m in result.value.models] == ["claude-opus-5-5"]
    assert result.value.from_anthropic is False
    assert "Add your Claude API key" in result.value.message


@pytest.mark.usefixtures("with_key")
def test_model_list_keeps_the_current_model_first_if_anthropic_omits_it(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    sonnet = OPUS.model_copy(update={"id": "claude-sonnet-5", "display_name": "Claude Sonnet 5"})
    fake_list(monkeypatch, Ok([sonnet]))
    result = settings.list_model_choices(settings_config)
    assert isinstance(result, Ok)
    assert [m.id for m in result.value.models] == ["claude-opus-5-5", "claude-sonnet-5"]


@pytest.mark.usefixtures("with_key")
def test_model_list_uses_anthropic_order_when_current_is_included(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_list(monkeypatch, Ok([OPUS]))
    result = settings.list_model_choices(settings_config)
    assert isinstance(result, Ok) and result.value.models == [OPUS]


@pytest.mark.usefixtures("with_key")
def test_model_list_with_rejected_key_or_failure(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_list(monkeypatch, Err(ErrorKind.AI_AUTH, "x"))
    rejected = settings.list_model_choices(settings_config)
    assert isinstance(rejected, Ok) and rejected.value.message == settings.KEY_REJECTED
    fake_list(monkeypatch, Err(ErrorKind.IO, "x"))
    assert settings.list_model_choices(settings_config) == Err(
        ErrorKind.IO, settings.UNREACHABLE, {}
    )


def test_update_model_saves_and_logs_the_change(
    settings_config: AppConfig, env_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    result = settings.update_model(settings_config, "claude-sonnet-5", "xhigh", False)
    assert isinstance(result, Ok)
    assert (result.value.model, result.value.effort, result.value.verifier_enabled) == (
        "claude-sonnet-5",
        "xhigh",
        False,
    )
    text = env_file.read_text()
    assert "ANTHROPIC_MODEL=claude-sonnet-5" in text and "VERIFIER_ENABLED=0" in text
    assert "model claude-opus-5-5 -> claude-sonnet-5" in caplog.text


@pytest.mark.parametrize(
    ("model", "effort", "message"),
    [
        ("", "high", settings.BAD_MODEL),
        ("Claude Opus!", "high", settings.BAD_MODEL),
        ("claude-opus-5-5", "extreme", settings.BAD_EFFORT),
    ],
)
def test_update_model_validation(
    settings_config: AppConfig, env_file: Path, model: str, effort: str, message: str
) -> None:
    result = settings.update_model(settings_config, model, effort, True)
    assert isinstance(result, Err) and result.kind is ErrorKind.VALIDATION
    assert result.message == message
    assert not env_file.exists()


def test_connection_actions_report_unreadable_settings(
    settings_config: AppConfig, env_file: Path
) -> None:
    env_file.mkdir()
    for result in (
        settings.test_connection(settings_config),
        settings.list_model_choices(settings_config),
        settings.update_model(settings_config, "claude-opus-5-5", "high", True),
    ):
        assert isinstance(result, Err) and result.message == settings.READ_FAILED


def test_update_model_reports_a_failed_save(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.actions.settings.settings_store.write_env_key",
        lambda *_: Err(ErrorKind.IO, "disk"),
    )
    result = settings.update_model(settings_config, "claude-opus-5-5", "high", True)
    assert isinstance(result, Err) and result.message == settings.SAVE_FAILED
