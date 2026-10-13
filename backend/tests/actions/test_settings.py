"""Settings actions: precedence, validation, plain-language messages."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.actions import settings
from app.config import AppConfig
from app.domain.models import SettingsView
from app.domain.result import Err, ErrorKind, Ok

KEY = "sk-" + "ant-" + "api03-" + "A" * 30 + "wxyz"


def value(result: object) -> SettingsView:
    assert isinstance(result, Ok), result
    assert isinstance(result.value, SettingsView)
    return result.value


def test_defaults_when_nothing_is_set(settings_config: AppConfig) -> None:
    assert value(settings.get_settings(settings_config)) == SettingsView(
        owner_name="Owner",
        model="claude-opus-5-5",
        effort="high",
        verifier_enabled=True,
        web_research_enabled=False,
        system_records_enabled=False,
        gap_analysis_enabled=True,
        value_enabled=False,
        currency="SGD",
        default_timezone="Asia/Singapore",
        key_set=False,
        key_last4="",
    )


def test_env_file_wins_then_environment_then_default(
    settings_config: AppConfig, env_file: Path
) -> None:
    env_file.write_text("OWNER_NAME=From file\nANTHROPIC_MODEL=\nVERIFIER_ENABLED=0\n")
    config = dataclasses.replace(
        settings_config,
        environ={"OWNER_NAME": "From environment", "ANTHROPIC_MODEL": "claude-env-model"},
    )
    view = value(settings.get_settings(config))
    assert view.owner_name == "From file"
    assert view.model == "claude-env-model"  # empty in .env falls back to the environment
    assert view.verifier_enabled is False
    assert view.effort == "high"


def test_key_from_the_environment_counts_as_set(settings_config: AppConfig) -> None:
    config = dataclasses.replace(settings_config, environ={"ANTHROPIC_API_KEY": KEY})
    view = value(settings.get_settings(config))
    assert view.key_set is True and view.key_last4 == "wxyz"


def test_update_profile_saves_and_trims(settings_config: AppConfig, env_file: Path) -> None:
    view = value(settings.update_profile(settings_config, "  Eric Yim  "))
    assert view.owner_name == "Eric Yim"
    assert "OWNER_NAME=Eric Yim" in env_file.read_text()


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "Eric\nYim"])
def test_update_profile_refuses_bad_names(settings_config: AppConfig, name: str) -> None:
    result = settings.update_profile(settings_config, name)
    assert result == Err(ErrorKind.VALIDATION, settings.BAD_NAME, {"field": "owner_name"})


def test_save_api_key_stores_it_and_returns_only_the_last_four(
    settings_config: AppConfig, env_file: Path
) -> None:
    view = value(settings.save_api_key(settings_config, f"  {KEY}\n"))
    assert view.key_set is True
    assert view.key_last4 == "wxyz"
    assert KEY not in view.model_dump_json()
    assert f"ANTHROPIC_API_KEY={KEY}\n" in env_file.read_text()


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-key",
        "sk-ant-short",
        "sk-ant-has space in it-aaaaaaaaaaaa",
        "sk-openai-" + "a" * 30,
    ],
)
def test_save_api_key_refuses_things_that_are_not_keys(
    settings_config: AppConfig, env_file: Path, bad: str
) -> None:
    result = settings.save_api_key(settings_config, bad)
    assert result == Err(ErrorKind.VALIDATION, settings.BAD_KEY, {"field": "anthropic_api_key"})
    assert not env_file.exists()


def test_save_failure_gives_a_plain_message(settings_config: AppConfig, env_file: Path) -> None:
    env_file.mkdir()
    result = settings.save_api_key(settings_config, KEY)
    assert isinstance(result, Err)
    assert result.kind is ErrorKind.IO
    assert result.message in (settings.SAVE_FAILED, settings.READ_FAILED)
    assert KEY not in result.message and KEY not in str(dict(result.details))


def test_read_failure_gives_a_plain_message(settings_config: AppConfig, env_file: Path) -> None:
    env_file.mkdir()
    result = settings.get_settings(settings_config)
    assert isinstance(result, Err) and result.message == settings.READ_FAILED


def test_write_validation_from_the_store_passes_through(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.actions.settings.settings_store.write_env_key",
        lambda *_: Err(ErrorKind.VALIDATION, "No control characters."),
    )
    assert settings.update_profile(settings_config, "Eric") == Err(
        ErrorKind.VALIDATION, "No control characters."
    )


@pytest.mark.parametrize(
    ("raw", "flag"), [("1", True), ("true", True), ("on", True), ("0", False), ("no", False)]
)
def test_switches_accept_common_spellings(
    settings_config: AppConfig, env_file: Path, raw: str, flag: bool
) -> None:
    env_file.write_text(f"VERIFIER_ENABLED={raw}\nWEB_RESEARCH_ENABLED={raw}\n")
    view = value(settings.get_settings(settings_config))
    assert view.verifier_enabled is flag and view.web_research_enabled is flag
