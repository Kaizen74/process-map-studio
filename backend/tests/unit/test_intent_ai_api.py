"""The intent AI jobs (P13a-2; API_CONTRACT.md → Intent; PRD §3.16, G16, criterion 100): S1 intent
proposes statements from the A.12 charter, IX_compare proposes design gaps quoting both sides, and
the checks and IX_verify turn down what isn't grounded (traps RT1, RT2 and RT8). Claude mocked."""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import update

from app.actions import intent_ai as actions
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind
from app.pipeline import context
from app.pipeline import intent_ai as pipeline
from app.repositories import audit, versions
from app.repositories.tables import MapVersion
from tests.unit.test_intent_api import CHARTER, Engagement, build
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.uploads import wait_for_jobs

MOCKS = Path(__file__).resolve().parents[1] / "fixtures" / "mock_responses"
EXTRACTED = "Claude proposed 6 intent statements: 4 passed the checks; 2 were turned down and are listed as rejected."  # noqa: E501
# The owner-stated rule the design-gap tests compare with SOP LC-07 §4 (illustrative only).
RULE = "Special loads are checked by the Load control lead before any plan is approved."
SOP_SIDE = "Special loads shall be checked against the acceptance checklist before loading."
CONFLICT = (
    "The intent has the Load control lead check special loads before plan approval; the SOP "
    "checks them against a checklist before loading."
)


def run(engagement: Engagement, url: str) -> dict[str, Any]:
    started = engagement.client.post(url)
    assert started.status_code == 202, started.text
    wait_for_jobs(engagement.client)
    job = engagement.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    return dict(job)


def statements(engagement: Engagement) -> list[dict[str, Any]]:
    return list(engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json())


def by_anchor(engagement: Engagement) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for s in statements(engagement):
        if s["verification_status"] == "verified":  # the traps RT1 and RT2 cite §4 and §3 too
            out.setdefault(s["anchor"], []).append(s)
    return out


def actions_logged(engagement: Engagement, target_type: str) -> list[str]:
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = audit.list_recent(session, engagement_id=engagement.eid)
    return [r["action"] for r in reversed(rows) if r["target_type"] == target_type]


# --- S1 intent ---------------------------------------------------------------------------------


def test_the_charter_gives_four_statements_and_the_traps_are_turned_down(
    engagement: Engagement,
) -> None:
    job = run(engagement, f"/api/engagements/{engagement.eid}/intent/extract")
    assert (job["type"], job["status"], job["message"]) == ("intent_extract", "done", EXTRACTED)
    assert job["usage"]["calls"] == 2  # S1 intent on the charter, then IX_verify
    rows = statements(engagement)
    kept = [r for r in rows if r["verification_status"] == "verified"]
    assert [(r["anchor"], r["kind"], r["scope"], r["element_label"], r["metric"],
             r["comparator"], r["target_value"], r["unit"]) for r in kept] == [
        ("§1", "target", "step", "Draft load plan", "lead_time_min", "at_least", 120, "min"),
        ("§2", "control_objective", "step", "Approve load plan", None, None, None, None),
        ("§3", "target", "step", "Load and return LIR", "wait_min", "at_most", 10, "min"),
        ("§4", "promise", "process", "", None, None, None, None),
    ]  # fmt: skip
    assert all(r["status"] == "proposed" and r["origin"] == "document" for r in rows)
    assert kept[1]["label"] == f"Quoted from {CHARTER} §2"
    assert kept[1]["quote"] == "Every load plan is approved before release to Ramp."
    # RT1: a quote that isn't in its passage (G4). RT2: 5 minutes where the charter says 10 (G5).
    rejected = [(r["text"], r["rejection_guardrail"]) for r in rows
                if r["verification_status"] == "rejected"]  # fmt: skip
    assert rejected == [
        ("Load sheets are issued at least 20 minutes before departure.", "G4"),
        ("The loading report reaches Load Control within 5 minutes of loading completion.", "G5"),
    ]
    rt2 = next(r for r in rows if r["rejection_guardrail"] == "G5")
    refused = engagement.client.patch(f"/api/intent/{rt2['id']}", json={"status": "confirmed"})
    assert refused.status_code == 409


def test_only_the_charter_is_sent_never_an_interview(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    real = context.call_stage

    def spy(*args: Any) -> Any:
        sent.append(json.dumps(args[4]))
        return real(*args)

    monkeypatch.setattr(pipeline, "call_stage", spy)
    run(engagement, f"/api/engagements/{engagement.eid}/intent/extract")
    assert len(sent) == 2
    assert 'kind=\\"policy_or_charter\\"' in sent[0]
    for kind in ("interview_transcript", "sop", "job_description"):
        assert f'kind=\\"{kind}\\"' not in sent[0], kind
    assert "Priya" not in "".join(sent)


def test_a_rerun_keeps_what_eric_decided(engagement: Engagement) -> None:
    url = f"/api/engagements/{engagement.eid}/intent/extract"
    run(engagement, url)
    first = by_anchor(engagement)
    confirmed = first["§2"][0]
    dismissed = first["§4"][0]
    client = engagement.client
    assert client.patch(f"/api/intent/{confirmed['id']}", json={"status": "confirmed"}).is_success
    assert client.patch(f"/api/intent/{dismissed['id']}", json={"status": "dismissed"}).is_success
    run(engagement, url)
    again = by_anchor(engagement)
    assert len(statements(engagement)) == 6  # no duplicate of what Eric decided
    assert [(s["id"], s["status"]) for s in again["§2"]] == [(confirmed["id"], "confirmed")]
    assert [(s["id"], s["status"]) for s in again["§4"]] == [(dismissed["id"], "dismissed")]
    assert again["§1"][0]["id"] != first["§1"][0]["id"]  # undecided proposals are replaced


def test_with_the_verifier_off_only_the_checks_decide(engagement: Engagement) -> None:
    body = {"model": "claude-opus-5-5", "effort": "high", "verifier_enabled": False}
    assert engagement.client.put("/api/settings/model", json=body).status_code == 200
    job = run(engagement, f"/api/engagements/{engagement.eid}/intent/extract")
    assert (job["message"], job["usage"]["calls"]) == (EXTRACTED, 1)


@pytest.fixture()
def planted(settings_config: AppConfig, tmp_path: Path) -> Iterator[tuple[Engagement, Path]]:
    """The engagement with its own copy of the mock answers, so a test can plant answers."""
    mocks = tmp_path / "mocks"
    shutil.copytree(MOCKS, mocks)
    config = dataclasses.replace(settings_config, mock_fixtures_dir=mocks)
    yield from ((e, mocks) for e in build(config))


def plant(mocks: Path, stage: str, answer: dict[str, Any]) -> None:
    for old in (mocks / stage).glob("*.json"):
        old.unlink()
    (mocks / stage / "default.json").write_text(json.dumps(answer), encoding="utf-8")


def test_the_verifier_turns_down_what_the_passages_dont_support(
    planted: tuple[Engagement, Path],
) -> None:
    engagement, mocks = planted
    plant(mocks, "IX_verify", {"verdicts": [
        {"item_ref": "v1", "verdict": "not_supported", "reason": "The passage sets no time."},
        {"item_ref": "v2", "verdict": "supported", "reason": "Stated."},
        {"item_ref": "v3", "verdict": "partial", "reason": "Partly stated."},
    ]})  # fmt: skip
    job = run(engagement, f"/api/engagements/{engagement.eid}/intent/extract")
    assert job["message"] == (
        "Claude proposed 6 intent statements: 3 passed the checks; 3 were turned down and are "
        "listed as rejected."
    )
    found = {s["anchor"]: s for s in statements(engagement) if s["rejection_guardrail"] != "G4"}
    assert found["§1"]["rejection_guardrail"] == "IXV"
    # No verdict for §4 and a partial one for §3: kept, for Eric to decide.
    assert [found[a]["verification_status"] for a in ("§2", "§4")] == ["verified", "verified"]


def test_nothing_to_read_is_explained(settings_config: AppConfig) -> None:
    from tests import fixture_engagement
    from tests.unit.test_draft_api import make_client, with_key

    for client in make_client(settings_config):
        built = fixture_engagement.build(with_key(client), ["interview_transcript.txt"])
        response = client.post(f"/api/engagements/{built.engagement_id}/intent/extract")
        assert (response.status_code, response.json()["error"]["message"]) == (
            409, actions.NO_INTENT_SOURCE)  # fmt: skip
        assert client.post("/api/engagements/nope/intent/extract").status_code == 404


# --- IX_compare --------------------------------------------------------------------------------


def documented_ref(engagement: Engagement, source: str, anchor: str) -> str:
    """The call-local ref (d1, d2, …) IX_compare sees for one documented passage."""
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        documents = actions._documented(session, engagement.eid)
    return next(s.ref for d in documents if d.source_name == source
                for s in d.segments if s.anchor == anchor)  # fmt: skip


def owner_rule(engagement: Engagement) -> str:
    response = engagement.add(scope="process", element_stable_key=None, text=RULE)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def gap(intent_ref: str, refs: list[str], documented: str, intent_quote: str,
        conflict: str = CONFLICT) -> dict[str, Any]:  # fmt: skip
    return {"intent_ref": intent_ref, "segment_ids": refs, "documented_quote": documented,
            "intent_quote": intent_quote, "conflict": conflict}  # fmt: skip


def test_a_design_gap_quotes_both_sides_and_waits_for_eric(
    planted: tuple[Engagement, Path],
) -> None:
    engagement, mocks = planted
    intent_id = owner_rule(engagement)
    d4 = documented_ref(engagement, "sop_LC-07.docx", "§4")
    plant(mocks, "IX_compare", {"conflicts": [
        gap("i1", [d4], SOP_SIDE, RULE),
        gap("i1", [], "", RULE),  # RT8: only the intent side is quoted
        gap("i1", [d4], SOP_SIDE, RULE, conflict=" ".join(["word"] * 26)),  # over 25 words
        gap("i1", [d4], "Special loads are checked twice by Ramp.", RULE),  # not in the SOP (G4)
        gap("i1", [d4], SOP_SIDE, "Special loads are always checked."),  # not the intent (G4)
        gap("i2", [d4], SOP_SIDE, RULE),  # a statement that wasn't sent (G3, not stored)
    ]})  # fmt: skip
    plant(mocks, "IX_verify", {"verdicts": [
        {"item_ref": "v1", "verdict": "supported", "reason": "Both sides say so."},
    ]})  # fmt: skip
    version_id = engagement.graph["version"]["id"]
    job = run(engagement, f"/api/versions/{version_id}/intent/compare")
    assert (job["type"], job["status"]) == ("intent_compare", "done")
    assert job["message"] == (
        "Claude proposed 6 design gaps: 1 passed the checks; 5 were turned down and are listed "
        "as rejected."
    )
    assert job["usage"]["calls"] == 2
    rows = engagement.client.get(f"/api/versions/{version_id}/intent/conflicts").json()
    assert [(r["verification_status"], r["rejection_guardrail"]) for r in rows] == [
        ("verified", None), ("rejected", "IX1"), ("rejected", "IX1"), ("rejected", "G4"),
        ("rejected", "G4"),
    ]  # fmt: skip
    first = rows[0]
    assert {k: first[k] for k in ("intent_id", "intent_text", "intent_label", "intent_quote",
                                  "source_name", "anchor", "quote", "conflict_text",
                                  "verifier_verdict", "status")} == {
        "intent_id": intent_id, "intent_text": RULE,
        "intent_label": "Target set by Load control lead, 1 Oct 2026", "intent_quote": RULE,
        "source_name": "sop_LC-07.docx", "anchor": "§4", "quote": SOP_SIDE,
        "conflict_text": CONFLICT, "verifier_verdict": "supported", "status": "proposed",
    }  # fmt: skip
    # Eric decides: the verified one can be confirmed; RT8 can't.
    url = f"/api/intent-conflicts/{first['id']}"
    confirmed = engagement.client.patch(url, json={"status": "confirmed", "note": "Checked."})
    assert (confirmed.json()["status"], confirmed.json()["note"]) == ("confirmed", "Checked.")
    refused = engagement.client.patch(f"/api/intent-conflicts/{rows[1]['id']}",
                                      json={"status": "confirmed"})  # fmt: skip
    assert (refused.status_code, refused.json()["error"]["message"]) == (
        409, actions.CONFLICT_REJECTED)  # fmt: skip
    long = engagement.client.patch(url, json={"note": "x" * 301})
    assert long.status_code == 422
    assert engagement.client.patch("/api/intent-conflicts/nope", json={}).status_code == 404
    assert actions_logged(engagement, "intent_conflict") == ["Confirmed design gap"]
    # A rerun keeps the confirmed one and doesn't propose it again.
    run(engagement, f"/api/versions/{version_id}/intent/compare")
    again = engagement.client.get(f"/api/versions/{version_id}/intent/conflicts").json()
    assert [(r["id"], r["status"]) for r in again if r["status"] == "confirmed"] == [
        (first["id"], "confirmed")]  # fmt: skip
    # Every new proposal pairing the same statement and passage is left out; RT8 cites none.
    assert [(r["status"], r["rejection_guardrail"]) for r in again] == [
        ("confirmed", None), ("proposed", "IX1")]  # fmt: skip


def test_compare_needs_a_draft_and_confirmed_intent(engagement: Engagement) -> None:
    version_id = engagement.graph["version"]["id"]
    url = f"/api/versions/{version_id}/intent/compare"
    client = engagement.client
    first = client.post(url)
    assert (first.status_code, first.json()["error"]["message"]) == (409, actions.NOTHING_CONFIRMED)
    owner_rule(engagement)
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        session.execute(update(MapVersion).where(MapVersion.id == version_id)
                        .values(state="published"))  # fmt: skip
    published = client.post(url)
    assert (published.status_code, published.json()["error"]["message"]) == (
        409, actions.NOT_A_DRAFT)  # fmt: skip
    assert client.post("/api/versions/nope/intent/compare").status_code == 404
    assert client.get("/api/versions/nope/intent/conflicts").status_code == 404


def test_design_gaps_carry_over_when_a_version_is_reopened(
    planted: tuple[Engagement, Path],
) -> None:
    engagement, mocks = planted
    owner_rule(engagement)
    d4 = documented_ref(engagement, "sop_LC-07.docx", "§4")
    plant(mocks, "IX_compare", {"conflicts": [gap("i1", [d4], SOP_SIDE, RULE)]})
    version_id = engagement.graph["version"]["id"]
    run(engagement, f"/api/versions/{version_id}/intent/compare")
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        fresh = versions.create(session, engagement_id=engagement.eid, label="v2", state="draft")
        versions.copy_content(session, version_id, fresh.id)
    copied = engagement.client.get(f"/api/versions/{fresh.id}/intent/conflicts").json()
    assert [(r["quote"], r["conflict_text"]) for r in copied] == [(SOP_SIDE, CONFLICT)]


def test_the_intent_jobs_use_the_ai_context(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a key and outside mock mode, the job fails in plain words and stores nothing."""
    monkeypatch.setattr(actions, "ai_context",
                        lambda config: Err(ErrorKind.VALIDATION, context.NO_KEY))  # fmt: skip
    job = run(engagement, f"/api/engagements/{engagement.eid}/intent/extract")
    assert (job["status"], job["error"]) == ("failed", context.NO_KEY)
    assert statements(engagement) == []
