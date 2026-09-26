"""Settings actions (PRD §3.4): what may be changed, validation and plain-language messages.

Values are read on every call (the .env file first, then the computer's environment, then the
PRD defaults), so changes take effect without restarting. The API key is never returned.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.config import SETTING_DEFAULTS, AppConfig
from app.domain.models import SettingsView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import settings_store

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
