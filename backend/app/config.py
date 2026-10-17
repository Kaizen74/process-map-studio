"""Application configuration read from environment variables (PRD §3.4).

Start-up values come from the environment. Settings Eric changes in the app (API key, model,
owner name, switches) live in the .env file, read and written through services/settings_store.py
by the settings actions, and take effect without restarting.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

APP_VERSION = "1.0.0"
PRD_VERSION = "1.5"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
# The HTML export uses the same design tokens and self-hosted fonts as the app (PRD §3.10).
DESIGN_TOKENS_FILE = REPO_ROOT / "shared" / "design_tokens.json"
FONTS_DIR = REPO_ROOT / "frontend" / "public" / "fonts"
# The Reality pack draws its views with the app's own Reality stylesheet (PRD §3.18.6, RQ4).
REALITY_CSS_FILE = REPO_ROOT / "frontend" / "src" / "components" / "reality" / "reality.css"
# Canned AI answers used when MOCK_CLAUDE=1 (PRD §3.7).
MOCK_FIXTURES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "mock_responses"

# PRD §3.4 defaults for settings read from .env, then the environment, then these.
SETTING_DEFAULTS: Mapping[str, str] = MappingProxyType(
    {
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_MODEL": "claude-opus-5-5",
        "ANTHROPIC_EFFORT": "high",
        "MOCK_CLAUDE": "0",
        "VERIFIER_ENABLED": "1",
        "WEB_RESEARCH_ENABLED": "0",
        "SYSTEM_RECORDS_ENABLED": "0",  # decision A: optional modules start off (R7)
        "GAP_ANALYSIS_ENABLED": "1",  # decision A: gap analysis starts on, as before (R10)
        "VALUE_ENABLED": "0",  # decision A: value calculator and dispositions start off (R10)
        "REALITY_VIEWS_ENABLED": "0",  # decision A: Reality views start off (P13a)
        "DEFAULT_TIMEZONE": "Asia/Singapore",  # §3.4: a new system log's time zone (R10)
        "WEB_SEARCH_TOOL_VERSION": "",
        "WEB_SEARCH_MAX_USES_CAP": "20",
        "OWNER_NAME": "Owner",
        "CURRENCY": "SGD",  # §3.4: the value calculator's currency (R9b; Settings Regional, R10)
    }
)


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_version: str
    prd_version: str
    port: int
    data_dir: Path
    frontend_dist: Path
    mock_claude: bool
    env_file: Path
    # Snapshot of the computer's environment variables at start-up.
    environ: Mapping[str, str]
    mock_fixtures_dir: Path = MOCK_FIXTURES_DIR


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Build the configuration from environment variables, with the PRD §3.4 defaults."""
    values = os.environ if env is None else env
    data_dir = Path(values.get("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    return AppConfig(
        app_version=APP_VERSION,
        prd_version=PRD_VERSION,
        port=int(values.get("APP_PORT", "8000")),
        data_dir=data_dir.resolve(),
        frontend_dist=DEFAULT_FRONTEND_DIST,
        mock_claude=values.get("MOCK_CLAUDE", "0") == "1",
        # PMS_ENV_FILE lets tests and the browser checks use a throwaway settings file.
        env_file=Path(values.get("PMS_ENV_FILE", str(DEFAULT_ENV_FILE))),
        environ=MappingProxyType(dict(values)),
    )
