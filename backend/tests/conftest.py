"""Shared test settings. Every test runs offline with Claude mocked (PRD constraint 13)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import AppConfig, load_config
from tests.paths import REPO_ROOT

os.environ.setdefault("MOCK_CLAUDE", "1")

REAL_ENV_FILE = REPO_ROOT / ".env"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


@pytest.fixture(autouse=True, scope="session")
def real_env_file_is_never_touched() -> Iterator[None]:
    """Guard: no test may change the real .env (it holds Eric's API key)."""
    before = _fingerprint(REAL_ENV_FILE)
    yield
    assert _fingerprint(REAL_ENV_FILE) == before, "a test changed the real .env file"


@pytest.fixture()
def env_file(tmp_path: Path) -> Path:
    """A throwaway settings file for one test."""
    return tmp_path / ".env"


@pytest.fixture()
def settings_config(env_file: Path) -> AppConfig:
    """App configuration pointing at the throwaway settings file, with an empty environment."""
    return load_config({"PMS_ENV_FILE": str(env_file), "MOCK_CLAUDE": "1"})
