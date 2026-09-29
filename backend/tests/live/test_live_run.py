"""The P12 live evaluation (PRD §6.3 P12): the illustrative fixture drafted twice by the real
Claude model, Analysis A and B on the first draft, scored against the thresholds.

Runs only when Eric asks (`pytest -m live`; the default suite leaves it out). It uses his key
from the OS environment or the local .env file, read only: the key is handed to a throwaway app
(its own data folder, no settings file) and is never written, printed or logged. It sends only
the illustrative fixture documents, never Eric's own data. Costs: two full drafts, one Analysis A
and one Analysis B (up to 10 web searches), billed to his Anthropic account.

The report (labels and counts only) is written to PMS_LIVE_REPORT, or to the test's temporary
folder, and printed; the test fails if a threshold is missed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import SETTING_DEFAULTS, load_config
from app.domain.result import Err, Ok, Result
from app.main import create_app
from app.services import ai_service, settings_store
from tests.conftest import REAL_ENV_FILE
from tests.live import capture, evaluation

pytestmark = pytest.mark.live

RUNS = 2
CARRIED = ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_EFFORT", "VERIFIER_ENABLED")


def eric_settings() -> dict[str, str]:
    """Eric's key, model, effort and verifier switch: .env first, then the OS environment."""
    from_file = settings_store.read_env(REAL_ENV_FILE)
    saved = from_file.value if isinstance(from_file, Ok) else {}
    return {
        name: saved.get(name) or os.environ.get(name) or SETTING_DEFAULTS[name] for name in CARRIED
    }


def record_format_problems(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep why an answer failed validation (the field and the rule, cut to 300 characters)."""
    validate = ai_service._validate

    def recording(model: type[BaseModel], text: str) -> Result[dict[str, object]]:
        result = validate(model, text)
        if isinstance(result, Err):
            capture.FORMAT_PROBLEMS.append(f"{model.__name__}: {result.message[:300]}")
        return result

    monkeypatch.setattr(ai_service, "_validate", recording)


@pytest.fixture()
def live_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    record_format_problems(monkeypatch)
    settings = eric_settings()
    if not settings["ANTHROPIC_API_KEY"].strip():
        pytest.skip("No Claude API key: add it in Settings (or ANTHROPIC_API_KEY) first.")
    config = load_config(
        {
            **settings,
            "MOCK_CLAUDE": "0",
            "PMS_ENV_FILE": str(tmp_path / ".env"),
            "DATA_DIR": str(tmp_path / "data"),
        }
    )
    with TestClient(create_app(config), raise_server_exceptions=False) as client:
        yield client


def save(report: str, tmp_path: Path) -> None:
    path = Path(os.environ.get("PMS_LIVE_REPORT", tmp_path / "live-evaluation.md"))
    path.write_text(report, encoding="utf-8")
    print(f"\n{report}\nReport saved to {path}")


def test_live_fixture_meets_the_p12_thresholds(live_client: TestClient, tmp_path: Path) -> None:
    model = eric_settings()["ANTHROPIC_MODEL"]
    try:
        runs = capture.capture_runs(live_client, RUNS)
    except AssertionError as failed:
        # A draft that fails still leaves a report: the error and the calls that went wrong.
        save(evaluation.render_failure(str(failed), capture.usage(live_client), model), tmp_path)
        raise
    per_run = [evaluation.evaluate_run(run) for run in runs]
    save(evaluation.render(runs, per_run, model), tmp_path)
    checks = [c for run_checks in per_run for c in run_checks] + [evaluation.stability(runs)]
    missed = [f"{c.code} {c.name}: {c.detail}" for c in checks if c.passed is False]
    assert not missed, "Thresholds missed:\n" + "\n".join(missed)
