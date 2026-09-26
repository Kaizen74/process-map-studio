"""Shared test settings. Every test runs offline with Claude mocked (PRD constraint 13)."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

# Before anything imports the app: tests (and any app they start, which inherits this
# environment) use a throwaway data folder and settings file, never Eric's real ones.
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="pms-tests-"))
os.environ["DATA_DIR"] = str(_SESSION_DIR / "data")
os.environ["PMS_ENV_FILE"] = str(_SESSION_DIR / ".env")
os.environ.setdefault("MOCK_CLAUDE", "1")

import pytest  # noqa: E402

from app.config import AppConfig, load_config  # noqa: E402
from tests.paths import REPO_ROOT  # noqa: E402

REAL_ENV_FILE = REPO_ROOT / ".env"
REAL_DATA_DIR = REPO_ROOT / "data"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _folder_fingerprint(folder: Path) -> list[tuple[str, int, int]]:
    if not folder.exists():
        return []
    return sorted(
        (str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns)
        for p in folder.rglob("*")
        if p.is_file()
    )


@pytest.fixture(autouse=True, scope="session")
def real_env_file_is_never_touched() -> Iterator[None]:
    """Guard: no test may change the real .env (it holds Eric's API key)."""
    before = _fingerprint(REAL_ENV_FILE)
    yield
    assert _fingerprint(REAL_ENV_FILE) == before, "a test changed the real .env file"


@pytest.fixture(autouse=True, scope="session")
def real_data_folder_is_never_touched() -> Iterator[None]:
    """Guard: no test may create or change anything in the real data folder (Eric's work)."""
    before = _folder_fingerprint(REAL_DATA_DIR)
    yield
    assert _folder_fingerprint(REAL_DATA_DIR) == before, "a test changed the real data folder"


@pytest.fixture()
def env_file(tmp_path: Path) -> Path:
    """A throwaway settings file for one test."""
    return tmp_path / ".env"


@pytest.fixture()
def settings_config(env_file: Path) -> AppConfig:
    """App configuration pointing at the throwaway settings file, with an empty environment."""
    return load_config(
        {
            "PMS_ENV_FILE": str(env_file),
            "MOCK_CLAUDE": "1",
            "DATA_DIR": str(env_file.parent / "data"),
        }
    )


@pytest.fixture()
def sessions(settings_config: AppConfig) -> Iterator[object]:
    """A migrated throwaway database for one test, with its session factory."""
    from app import db

    path = db.db_path(settings_config.data_dir)
    db.upgrade(path)
    engine = db.make_engine(path)
    yield db.session_factory(engine)
    engine.dispose()
