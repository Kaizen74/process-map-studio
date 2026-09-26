"""Settings actions (PRD §3.4): what may be changed, validation and plain-language messages.

Values are read on every call (the .env file first, then the computer's environment, then the
PRD defaults), so changes take effect without restarting. The API key is never returned.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.config import SETTING_DEFAULTS, AppConfig
from app.db import session_scope
from app.domain.models import (
    AiUsage,
    ConnectionCapabilities,
    ConnectionTest,
    ModelChoices,
    ModelSummary,
    SettingsView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import ai_calls, audit
from app.services import ai_service, settings_store

log = logging.getLogger(__name__)

SAVE_FAILED = (
    "Your settings couldn't be saved to the .env file in the app folder. "
    "Check the folder isn't read-only or open in another program, then try again."
)
READ_FAILED = (
    "Your settings couldn't be read from the .env file in the app folder. "
    "Check the file isn't open in another program, then try again."
)
BAD_NAME = "Please enter your name (up to 80 characters, no line breaks)."
BAD_KEY = (
    "That doesn't look like a Claude API key. Keys start with sk-ant-. "
    "Copy it again from the Claude Console."
)
NO_KEY = "Add your Claude API key first, then test the connection."
KEY_REJECTED = "Your API key was rejected. Copy it again from the Claude Console and paste it here."
BUSY = "Anthropic is busy right now, so the check couldn't finish. Try again in a minute."
UNREACHABLE = (
    "The app couldn't reach Anthropic. Check your internet connection (and any company proxy), "
    "then try again."
)
BAD_MODEL = "Please choose a model from the list."
BAD_EFFORT = "Please choose an effort level: low, medium, high, xhigh or max."
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
_MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,63}$")
_KEY_SHAPE = re.compile(r"^sk-ant-[A-Za-z0-9_\-]{13,293}$")


def effective_settings(config: AppConfig) -> Result[dict[str, str]]:
    """Every setting's current value: non-empty .env value, else environment, else default."""
    match settings_store.read_env(config.env_file):
        case Err() as err:
            return Err(err.kind, READ_FAILED, err.details)
        case Ok(value=from_file):
            pass
    values: dict[str, str] = {}
    for name, default in SETTING_DEFAULTS.items():
        values[name] = from_file.get(name) or config.environ.get(name) or default
    return Ok(values)


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _view(values: Mapping[str, str]) -> SettingsView:
    key = values["ANTHROPIC_API_KEY"].strip()
    return SettingsView(
        owner_name=values["OWNER_NAME"],
        model=values["ANTHROPIC_MODEL"],
        effort=values["ANTHROPIC_EFFORT"],
        verifier_enabled=_flag(values["VERIFIER_ENABLED"]),
        web_research_enabled=_flag(values["WEB_RESEARCH_ENABLED"]),
        key_set=bool(key),
        key_last4=settings_store.mask_key(key),
    )


def get_settings(config: AppConfig) -> Result[SettingsView]:
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            return Ok(_view(values))


def _save(config: AppConfig, name: str, value: str) -> Result[SettingsView]:
    match settings_store.write_env_key(config.env_file, name, value):
        case Err(kind=ErrorKind.VALIDATION) as err:
            return Err(ErrorKind.VALIDATION, err.message)
        case Err() as err:
            return Err(err.kind, SAVE_FAILED, err.details)
        case Ok():
            return get_settings(config)


def update_profile(config: AppConfig, owner_name: str) -> Result[SettingsView]:
    """Save the name shown as validator on published versions and exports."""
    name = owner_name.strip()
    if not name or len(name) > 80 or any(ch in name for ch in "\r\n\t"):
        return Err(ErrorKind.VALIDATION, BAD_NAME, {"field": "owner_name"})
    return _save(config, "OWNER_NAME", name)


def save_api_key(config: AppConfig, api_key: str) -> Result[SettingsView]:
    """Save the Claude API key to .env. The key itself is never returned or put in a message."""
    key = api_key.strip()
    if not _KEY_SHAPE.match(key):
        return Err(ErrorKind.VALIDATION, BAD_KEY, {"field": "anthropic_api_key"})
    return _save(config, "ANTHROPIC_API_KEY", key)


def _connection(config: AppConfig, values: Mapping[str, str]) -> ai_service.AiConnection:
    return ai_service.AiConnection(
        api_key=values["ANTHROPIC_API_KEY"].strip(),
        mock=_flag(values["MOCK_CLAUDE"]),
        fixtures_dir=config.mock_fixtures_dir,
    )


def _ai_failure(err: Err) -> Err:
    """Plain-language errors for failures that aren't a verdict on the key or model."""
    if err.kind is ErrorKind.AI_RATE_LIMIT:
        return Err(ErrorKind.AI_RATE_LIMIT, BUSY, err.details)
    return Err(ErrorKind.IO, UNREACHABLE, err.details)


def test_connection(config: AppConfig) -> Result[ConnectionTest]:
    """Check the saved key and the configured model with the Models API (PRD §3.4)."""
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    model = values["ANTHROPIC_MODEL"]
    none = ConnectionCapabilities(pdf_input=False, structured_outputs=False)
    if not values["ANTHROPIC_API_KEY"].strip():
        return Ok(
            ConnectionTest(
                key_valid=False, model_available=False, capabilities=none, message=NO_KEY
            )
        )

    match ai_service.get_model(_connection(config, values), model):
        case Ok(value=summary):
            return Ok(
                ConnectionTest(
                    key_valid=True,
                    model_available=True,
                    capabilities=ConnectionCapabilities(
                        pdf_input=summary.pdf_input, structured_outputs=summary.structured_outputs
                    ),
                    message=f"Connected. Your key works and {model} is available.",
                )
            )
        case Err(kind=ErrorKind.AI_AUTH):
            return Ok(
                ConnectionTest(
                    key_valid=False, model_available=False, capabilities=none, message=KEY_REJECTED
                )
            )
        case Err(kind=ErrorKind.NOT_FOUND):
            return Ok(
                ConnectionTest(
                    key_valid=True,
                    model_available=False,
                    capabilities=none,
                    message=(
                        f"Your key works, but the model {model} isn't available to your account. "
                        "Choose another model in the Model card."
                    ),
                )
            )
        case Err() as err:
            return _ai_failure(err)


def list_model_choices(config: AppConfig) -> Result[ModelChoices]:
    """Models for the dropdown: the key's models from Anthropic, or just the configured one."""
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    current = ModelSummary(
        id=values["ANTHROPIC_MODEL"],
        display_name=values["ANTHROPIC_MODEL"],
        pdf_input=False,
        structured_outputs=False,
        effort_levels=list(EFFORT_LEVELS),
    )
    if not values["ANTHROPIC_API_KEY"].strip():
        return Ok(
            ModelChoices(
                models=[current],
                from_anthropic=False,
                message="Add your Claude API key to see every model available to you.",
            )
        )
    match ai_service.list_models(_connection(config, values)):
        case Ok(value=models):
            if not any(m.id == current.id for m in models):
                models = [current, *models]
            return Ok(ModelChoices(models=models, from_anthropic=True, message=""))
        case Err(kind=ErrorKind.AI_AUTH):
            return Ok(ModelChoices(models=[current], from_anthropic=False, message=KEY_REJECTED))
        case Err() as err:
            return _ai_failure(err)


def update_model(
    config: AppConfig,
    model: str,
    effort: str,
    verifier_enabled: bool,
    *,
    sessions: sessionmaker[Session] | None = None,
) -> Result[SettingsView]:
    """Save the model, effort and verifier switch; log it and write an audit row (PRD §3.4)."""
    model = model.strip()
    if not _MODEL_ID.match(model):
        return Err(ErrorKind.VALIDATION, BAD_MODEL, {"field": "model"})
    if effort not in EFFORT_LEVELS:
        return Err(ErrorKind.VALIDATION, BAD_EFFORT, {"field": "effort"})
    match get_settings(config):
        case Err() as err:
            return err
        case Ok(value=before):
            pass
    for name, value in (
        ("ANTHROPIC_MODEL", model),
        ("ANTHROPIC_EFFORT", effort),
        ("VERIFIER_ENABLED", "1" if verifier_enabled else "0"),
    ):
        match _save(config, name, value):
            case Err() as err:
                return err
            case Ok():
                pass
    log.info(
        "Model settings changed: model %s -> %s, effort %s -> %s, verifier %s -> %s",
        before.model,
        model,
        before.effort,
        effort,
        before.verifier_enabled,
        verifier_enabled,
    )
    if sessions is not None:
        with session_scope(sessions) as session:
            audit.record(
                session,
                actor=before.owner_name,
                action="Changed model settings",
                target_type="settings",
                target_id="model",
                before={
                    "model": before.model,
                    "effort": before.effort,
                    "verifier_enabled": before.verifier_enabled,
                },
                after={"model": model, "effort": effort, "verifier_enabled": verifier_enabled},
            )
    return get_settings(config)


USAGE_LIMIT = (1, 500)
BAD_LIMIT = "Choose how many AI calls to show: 1 to 500."


def list_usage(sessions: sessionmaker[Session], limit: int) -> Result[AiUsage]:
    """The most recent AI calls and the totals of every call (usage only, never text)."""
    low, high = USAGE_LIMIT
    if not low <= limit <= high:
        return Err(ErrorKind.VALIDATION, BAD_LIMIT, {"field": "limit"})
    with session_scope(sessions) as session:
        return Ok(AiUsage(items=ai_calls.recent(session, limit), totals=ai_calls.totals(session)))
