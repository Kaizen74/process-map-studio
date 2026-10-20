"""Golden baselines (PRD §6.2 item 4): byte-identical outcomes on the illustrative fixture.

- G1: the graph JSON of the sample engagement's draft (PRD Appendix A.5).
- G2: the layout JSON of that draft (PRD §3.9): where every lane, step and line is drawn; G2a and
  G2b the layout of each view (As done, As documented; §3.12.11).
- G3: the Master Process Map Markdown of the sample, fully confirmed and published (PRD §7.3).
- G4: the alignment-matrix payload of that draft (PRD §4 Views, §5.4 Matrix).
- G5: the single-file HTML map of the same published version (the embedded font data, which is the
  unchanged font files, is replaced by its size so the baseline stays readable).
- G6: the outcome of the hallucination-trap run (Appendix A.6): what was rejected, where and why,
  and the map that is left. None of the traps may reach the graph.
- G7: the gap-analysis reports of the sample (Appendix A.7): Analysis A, and Analysis B from the
  mocked web search with traps TE1-TE9, as reported and, after a fixed set of decisions, as
  exported (run and finalise times replaced).
- G8: the sensemaking outputs of the sample (Appendix A.8): per step its work type with the
  quoted cues, the interview accounts it rests on (official, lived or unclear, with the cue and
  any stated reason), its know-how and stories; the glossary, the capability notes and the
  coverage report with its follow-up questions and probes.
- G9: the three standard interview templates (PRD Appendix F.9) in Markdown, as downloaded.
- G10: the system-records outputs from fixture A.11 (P10b R12; `test_golden_g10.py`).

Record IDs and times change on every run, so each ID is replaced by a stable token in order of
first appearance. To accept a legitimate change, run the tests with PMS_UPDATE_GOLDEN=1, review the
diff of the baseline file, and log the reason in DECISIONS.md (PRD §6.2 rules). To show Eric a
change before it is accepted, run with PMS_GOLDEN_CANDIDATES=<folder>: each output is also written
there under its baseline's name, and the baselines are left alone (2026-10-06).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import publish as publish_action
from app.config import AppConfig
from app.main import create_app
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

HERE = Path(__file__).resolve().parent
FRONTEND_FIXTURES = HERE.parents[2] / "frontend" / "tests" / "fixtures"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
KEY = "sk-" + "ant-" + "api03-" + "G0lden" * 7 + "Pq1z"


def stable_ids(data: Any) -> Any:
    """Replace every UUID with `id-1`, `id-2` … in order of first appearance."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    tokens: dict[str, str] = {}

    def token(match: re.Match[str]) -> str:
        return tokens.setdefault(match.group(0), f"id-{len(tokens) + 1}")

    return json.loads(UUID.sub(token, text))


def write_candidate(name: str, rendered: str) -> None:
    """With PMS_GOLDEN_CANDIDATES set, the output also goes there for Eric to review."""
    folder = os.environ.get("PMS_GOLDEN_CANDIDATES")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / name).write_text(rendered, encoding="utf-8")


def matches_baseline(name: str, data: Any, folder: Path = HERE) -> None:
    rendered = json.dumps(stable_ids(data), indent=2, ensure_ascii=False) + "\n"
    write_candidate(name, rendered)
    path = folder / name
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


def test_g2a_and_g2b_layout_of_each_view(settings_config: AppConfig) -> None:
    """PRD §3.12.11 (V1): the layout of As done (G2a) and of As documented (G2b)."""
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        url = f"/api/versions/{version_id}/layout"
        matches_baseline("G2a_layout_done.json", client.get(url, params={"view": "done"}).json())
        documented = client.get(url, params={"view": "documented"}).json()
        matches_baseline("G2b_layout_documented.json", documented)


def test_g4_alignment_matrix_of_the_sample(settings_config: AppConfig) -> None:
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        matrix = client.get(f"/api/versions/{version_id}/alignment-matrix").json()
        matches_baseline("G4_alignment_matrix.json", matrix)


def test_g8_sensemaking_of_the_sample(settings_config: AppConfig) -> None:
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        steps = []
        for e in graph["elements"]:
            if e["kind"] in {"start", "end"}:
                continue
            detail = client.get(f"/api/elements/{e['id']}").json()
            steps.append({
                "label": e["label"],
                "work_type": e["work_type"],
                "constraint_type": e["constraint_type"],
                "work_type_status": e["work_type_status"],
                "work_type_cues": [c["quote"] for c in e["work_type_basis"]],
                "accounts": [
                    {k: a[k] for k in ("anchor", "account_type", "account_cue", "stated_reason",
                                       "variation_condition", "question_id")}
                    for a in detail["answers"]
                ],
                "account_summary": e["account_summary"],
                "know_how": detail["know_how"],
                "stories": detail["stories"],
            })  # fmt: skip
        bundle = {
            "steps": steps,
            "glossary": client.get(f"/api/versions/{version_id}/glossary").json(),
            "capability_notes": client.get(f"/api/versions/{version_id}/capability-notes").json(),
            "coverage": client.get(f"/api/versions/{version_id}/coverage").json(),
        }
        matches_baseline("G8_sensemaking.json", bundle)


def test_the_frontend_sample_matches_the_backend(settings_config: AppConfig) -> None:
    """The frontend tests draw the sample map from this file (graph, layout, every step's panel
    details and the cited sources' passages, one set of IDs). Not a PRD baseline: it keeps the
    frontend fixture honest. Rewritten with PMS_UPDATE_GOLDEN=1 like the baselines."""
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        layout = client.get(f"/api/versions/{version_id}/layout").json()
        elements = {
            e["id"]: client.get(f"/api/elements/{e['id']}").json() for e in graph["elements"]
        }
        # In order of first citation (IDs are random, so sorting them would reorder the file).
        cited = dict.fromkeys(
            c["source_id"] for e in elements.values() for c in e["evidence"] if c["segment_id"]
        )
        segments = {s: client.get(f"/api/sources/{s}/segments").json() for s in cited}
        # V2: each view's layout and graph (As done with the other view ghosted too).
        url = f"/api/versions/{version_id}"
        views = {
            "done": client.get(f"{url}/layout", params={"view": "done"}).json(),
            "documented": client.get(f"{url}/layout", params={"view": "documented"}).json(),
            "done_with_other": client.get(
                f"{url}/layout", params={"view": "done", "show_other": "1"}
            ).json(),
        }
        view_graphs = {
            v: client.get(f"{url}/graph", params={"view": v}).json() for v in ("done", "documented")
        }
        # X2: the exceptions report of each view (the Exceptions lens and register).
        exceptions = {
            v: client.get(f"{url}/exceptions", params={"view": v}).json()
            for v in ("done", "documented")
        }
        # P9u: the Registers lists made from the interviews.
        lists = {name: client.get(f"{url}/{name}").json()
                 for name in ("stories", "glossary", "capability-notes")}  # fmt: skip
        bundle = {"graph": graph, "layout": layout, "elements": elements, "segments": segments,
                  "views": views, "view_graphs": view_graphs,
                  "exceptions": exceptions, "lists": lists}  # fmt: skip
        matches_baseline("sample_map.json", bundle, FRONTEND_FIXTURES)


def test_the_frontend_documents_only_sample_matches_the_backend(settings_config: AppConfig) -> None:
    """The documents-only sample (Eric, 2026-10-20) as the frontend draws it: the graph and each
    view's graph and layout. Every step is documented only, so As done has no step. Not a PRD
    baseline; rewritten with PMS_UPDATE_GOLDEN=1 like the baselines."""
    for client, version_id in drafted(settings_config, make_ai_fixtures.DOCUMENTS_ONLY):
        url = f"/api/versions/{version_id}"
        bundle = {
            "graph": client.get(f"{url}/graph").json(),
            "views": {v: client.get(f"{url}/layout", params={"view": v}).json()
                      for v in ("done", "documented")},
            "view_graphs": {v: client.get(f"{url}/graph", params={"view": v}).json()
                            for v in ("done", "documented")},
        }  # fmt: skip
        matches_baseline("documents_only_map.json", bundle, FRONTEND_FIXTURES)


PUBLISHED_AT = "2026-09-28T09:00:00+00:00"
FONT_DATA = re.compile(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)")


def matches_text_baseline(name: str, text: str) -> None:
    tokens: dict[str, str] = {}

    def token(match: re.Match[str]) -> str:
        return tokens.setdefault(match.group(0), f"id-{len(tokens) + 1}")

    rendered = UUID.sub(token, text)
    rendered = FONT_DATA.sub(
        lambda m: f"data:font/woff2;base64,<{len(m.group(1))} characters>", rendered
    )
    write_candidate(name, rendered)
    path = HERE / name
    if os.environ.get("PMS_UPDATE_GOLDEN") == "1":
        path.write_text(rendered, encoding="utf-8")
    assert path.exists(), f"missing baseline {name}: run with PMS_UPDATE_GOLDEN=1 and review it"
    assert rendered == path.read_text(encoding="utf-8"), f"{name} differs from the baseline"


def published_exports(
    config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, str]]:
    """The sample draft with every step confirmed, published at a fixed time by "Owner"."""
    monkeypatch.setattr(publish_action, "now", lambda: PUBLISHED_AT)
    for client, version_id in drafted(config, fixture_engagement.SOURCES):
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        for element in graph["elements"]:
            if element["kind"] not in ("start", "end"):
                assert client.post(f"/api/elements/{element['id']}/confirm").status_code == 200
        response = client.post(f"/api/versions/{version_id}/publish")
        assert response.status_code == 200, response.text
        yield client, version_id


def test_g3_master_map_of_the_sample(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    for client, version_id in published_exports(settings_config, monkeypatch):
        md = client.get(f"/api/versions/{version_id}/export/md").text
        matches_text_baseline("G3_master_map.md", md)
        assert "Priya" not in md


def test_g5_html_map_of_the_sample(
    settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    for client, version_id in published_exports(settings_config, monkeypatch):
        html = client.get(f"/api/versions/{version_id}/export/html").text
        matches_text_baseline("G5_map.html", html)
        assert "Priya" not in html


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


# --- G7: the gap-analysis reports of the sample (PRD Appendix A.7; phase P10) -------------------

TIMES = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?")
DATES = re.compile(r"\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}\b")


def without_times(data: Any) -> Any:
    """Run and finalise times change on every run: each becomes "<time>"."""
    return json.loads(TIMES.sub("<time>", json.dumps(data, ensure_ascii=False)))


def test_g7_gap_reports_of_the_sample(settings_config: AppConfig) -> None:
    """Analysis A on the sample draft and Analysis B from the mocked web search (the A.7 traps),
    as reported; then both finalised after a fixed set of decisions, as exported."""
    for client, version_id in drafted(settings_config, fixture_engagement.SOURCES):
        drain = client.app.state.worker.drain  # type: ignore[attr-defined]
        [engagement] = client.get("/api/engagements").json()
        started = client.post(f"/api/versions/{version_id}/gap-analyses/internal").json()
        assert drain(60)
        internal = client.get(f"/api/gap-analyses/{started['analysis_id']}").json()
        url = f"/api/engagements/{engagement['id']}"
        assert client.patch(url, json=fixture_engagement.GAP_SETUP).status_code == 200
        brief = client.post(f"/api/versions/{version_id}/gap-analyses/external").json()
        gid = brief["analysis"]["id"]
        body = {"brief": brief["brief"]["brief"], "confirmed": True}
        assert client.patch(f"/api/gap-analyses/{gid}/brief", json=body).status_code == 200
        client.put("/api/settings/research", json={"web_research_enabled": True})
        assert client.post(f"/api/gap-analyses/{gid}/run").status_code == 202
        assert drain(60)
        external = client.get(f"/api/gap-analyses/{gid}").json()
        matches_baseline(
            "G7_gap_reports.json", without_times({"internal": internal, "external": external})
        )

        exports = []
        for report in (internal, external):
            for f in report["findings"] + report["questions"]:
                decision = (
                    {"disposition": "added_question"}
                    if f["severity"] in ("high", None)
                    else {"disposition": "dismissed", "note": "Checked with the process owner."}
                )
                response = client.patch(f"/api/gap-findings/{f['id']}", json=decision)
                assert response.status_code == 200, response.text
            analysis = report["analysis"]["id"]
            assert client.post(f"/api/gap-analyses/{analysis}/finalise").status_code == 200
            exports.append(client.get(f"/api/gap-analyses/{analysis}/export").text)
        matches_text_baseline("G7_gap_exports.md", DATES.sub("<date>", "\n---\n\n".join(exports)))


# --- G9: the standard interview templates (PRD Appendix F.9; phase P1) ------------------------


@pytest.mark.parametrize("kind", ["landscape", "practice", "follow_up"])
def test_g9_standard_interview_templates(settings_config: AppConfig, kind: str) -> None:
    """The Markdown template of each type, exactly as downloaded (approved by Eric 2026-09-30)."""
    with TestClient(create_app(settings_config)) as client:
        response = client.get("/api/templates/interview", params={"type": kind, "format": "md"})
        assert response.status_code == 200, response.text
        matches_text_baseline(f"G9_template_{kind}.md", response.text)
