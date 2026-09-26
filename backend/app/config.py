"""Application configuration read from environment variables (PRD §3.4).

Phase P0a reads only what the running shell needs. The .env file (API key, model, owner name)
is read and written through services/settings_store.py from phase P0b.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_VERSION = "0.1.0"
PRD_VERSION = "1.5"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_version: str
    prd_version: str
    port: int
    data_dir: Path
    frontend_dist: Path
    mock_claude: bool


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
    )
