"""Golden baselines (PRD §6.2 item 4): byte-identical outcomes on the illustrative fixture.

- G1: the graph JSON of the sample engagement's draft (PRD Appendix A.5).
- G2: the layout JSON of that draft (PRD §3.9): where every lane, step and line is drawn.
- G6: the outcome of the hallucination-trap run (Appendix A.6): what was rejected, where and why,
  and the map that is left. None of the traps may reach the graph.

Record IDs and times change on every run, so each ID is replaced by a stable token in order of
first appearance. To accept a legitimate change, run the tests with PMS_UPDATE_GOLDEN=1, review the
diff of the baseline file, and log the reason in DECISIONS.md (PRD §6.2 rules).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

HERE = Path(__file__).resolve().parent
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
KEY = "sk-" + "ant-" + "api03-" + "G0lden" * 7 + "Pq1z"


def stable_ids(data: Any) -> Any:
    """Replace every UUID with `id-1`, `id-2` … in order of first appearance."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    tokens: dict[str, str] = {}

    def token(match: re.Match[str]) -> str:
        return tokens.setdefault(match.group(0), f"id-{len(tokens) + 1}")

    return json.loads(UUID.sub(token, text))


def matches_baseline(name: str, data: Any) -> None:
    rendered = json.dumps(stable_ids(data), indent=2, ensure_ascii=False) + "\n"
    path = HERE / name
    if os.environ.get("PMS_UPDATE_GOLDEN") == "1":
        path.write_text(rendered, encoding="utf-8")
    assert path.exists(), f"missing baseline {name}: run with PMS_UPDATE_GOLDEN=1 and review it"
    assert rendered == path.read_text(encoding="utf-8"), f"{name} differs from the baseline"


def drafted(config: AppConfig, sources: list[str]) -> Iterator[tuple[TestClient, str]]:
    with TestClient(create_app(config)) as client:
        assert client.put("/api/settings/key", json={"anthropic_api_key": KEY}).status_code == 200
        built = fixture_engagement.build(client, sources)
        job_id = client.post(f"/api/engagements/{built.engagement_id}/draft").json()["job_id"]
        assert client.app.state.worker.drain(60)  # type: ignore[attr-defined]
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "done", job
        yield client, job["target_id"]


def test_g1_graph_of_the_sample(settings_config: AppConfig) -> None:
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        matches_baseline("G1_graph.json", graph)


def test_g2_layout_of_the_sample(settings_config: AppConfig) -> None:
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        layout = client.get(f"/api/versions/{version_id}/layout").json()
        matches_baseline("G2_layout.json", layout)


def test_g6_trap_outcome(settings_config: AppConfig) -> None:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=make_ai_fixtures.TRAPS)
    for client, version_id in drafted(config, make_ai_fixtures.TRAP_SOURCES):
        register = client.get(f"/api/versions/{version_id}/rejected-claims").json()
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        rejected = [
            {k: item[k] for k in ("claim_text", "guardrail", "stage", "reason", "source_name")}
            for item in register["items"]
        ]
        outcome = {
            "rejected": rejected,
            "scrub_count": register["scrub_count"],
            "map": [
                {k: e[k] for k in ("kind", "label", "needs_check", "review_status")}
                for e in graph["elements"]
            ],
        }
        matches_baseline("G6_traps.json", outcome)
        # None of the planted claims reaches the map (A.6), and the scrubbed name never appears.
        text = json.dumps(graph)
        for trap in ("T1", "T2", "T3", "T4", "T5", "fuel", "30 min", "Duty manager", "IATA"):
            assert trap not in text, trap
        assert "Priya" not in text
        assert {r["guardrail"] for r in rejected} == {"G3", "G4", "G5", "G6"}
