"""Gap analysis A, documents vs practice (API_CONTRACT.md → Gap analysis; PRD §3.11.1, Appendix
A.7, §6.3 P10) on the illustrative Appendix A draft, Claude mocked."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.result import Err, ErrorKind, Ok
from app.pipeline import ga_internal
from app.pipeline.ga_internal import DivergenceSet
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def run(d: Drafted, version_id: str | None = None) -> dict[str, Any]:
    response = d.client.post(f"/api/versions/{version_id or d.version_id}/gap-analyses/internal")
    assert response.status_code == 202, response.text
    started = response.json()
    assert d.client.app.state.worker.drain(60)  # type: ignore[attr-defined]
    job = d.client.get(f"/api/jobs/{started['job_id']}").json()
    report = d.client.get(f"/api/gap-analyses/{started['analysis_id']}")
    assert report.status_code == 200, report.text
    return {"job": job, **report.json()}


def dset(d: Drafted) -> DivergenceSet:
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        found = ga_internal.divergence_set(session, d.version_id)
    assert found is not None
    return found


# --- A.7 on the sample ---------------------------------------------------------------------------


def test_a7_the_expected_findings_and_severities(drafted: Drafted) -> None:
    graph_before = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    body = run(drafted)
    job = body["job"]
    assert job["status"] == "done", job
    assert job["type"] == "gap_internal" and job["target_id"] == body["analysis"]["id"]
    assert [s["status"] for s in job["stages"]] == ["done"] * 5
    assert job["usage"]["calls"] == 2  # GA_internal and GA_verify
    assert job["message"] == (
        "The documents-vs-practice report is ready: 4 findings, 1 question for your SMEs, "
        "0 rejected findings."
    )
    found = [
        (f["finding_type"], f["severity"], [e["label"] for e in f["elements"]], f["provenance"])
        for f in body["findings"]
    ]
    # Facts, high severity first, then in the order Claude gave them.
    assert found == [
        ("dead_control_candidate", "high", ["Approve load plan"], "O"),
        ("ownership_mismatch", "high", ["Deviation in limits?"], "O"),
        ("threshold_gap", "medium", ["Load and return LIR"], "O"),
        ("undocumented_work", "medium", ["Resolve or offload"], "O"),
    ]
    assert all(f["verifier_verdict"] == "supported" for f in body["findings"])
    assert all(f["disposition"] == "open" and not f["needs_check"] for f in body["findings"])
    assert body["rejected"] == []
    analysis = body["analysis"]
    assert (analysis["mode"], analysis["status"], analysis["version_label"]) == (
        "internal",
        "draft_report",
        "v0.1",
    )
    assert analysis["counts"] == {"kept": 4, "rejected": 0, "open": 5, "needs_check": 0}
    assert body["usage"]["calls"] == 2 and body["search_count"] == 0 and body["sources"] == []
    # The map is unchanged by the analysis (constraint 22).
    graph_after = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    assert graph_after == graph_before


def test_a7_every_finding_has_evidence_from_each_side(drafted: Drafted) -> None:
    findings = {f["finding_type"]: f for f in run(drafted)["findings"]}

    def sides(kind: str) -> list[tuple[str, str, str, str]]:
        return [
            (e["side"], e["source_name"], e["anchor"], e["stance"])
            for e in findings[kind]["evidence"]
        ]

    # SOP LC-07 §3.2 + JD Load control lead (supports) · interview silent
    assert sides("dead_control_candidate") == [
        ("documents", "sop LC-07", "§3.2", "supports"),
        ("documents", "jd load control lead", "¶ 2", "supports"),
        ("practice", "interview transcript", "", "silent"),
    ]
    # SOP RP-02 §2 · interview 21:50
    assert sides("threshold_gap") == [
        ("documents", "sop RP-02", "§2", "contradicts"),
        ("practice", "interview transcript", "21:50", "supports"),
    ]
    # SOP LC-07 §5 · interview 27:15 (the job descriptions are silent, but the SOP speaks)
    assert sides("ownership_mismatch") == [
        ("documents", "sop LC-07", "§5", "contradicts"),
        ("practice", "interview transcript", "27:15", "supports"),
    ]
    # interview 16:22 · SOPs and job descriptions silent
    assert sides("undocumented_work") == [
        ("practice", "interview transcript", "16:22", "supports"),
        ("documents", "jd load control lead", "", "silent"),
        ("documents", "jd load controller", "", "silent"),
        ("documents", "sop LC-07", "", "silent"),
        ("documents", "sop RP-02", "", "silent"),
    ]
    quoted = findings["threshold_gap"]["evidence"]
    assert [e["quote"] for e in quoted] == [
        "return the loading report to Load Control within 10 minutes of loading completion",
        "We sometimes wait fifteen minutes for it",
    ]
    assert all(e["segment_id"] for e in quoted)


def test_a7_the_unexplained_cause_becomes_a_question_not_a_guess(drafted: Drafted) -> None:
    body = run(drafted)
    [question] = body["questions"]
    assert question["question"] == (
        "Is the load plan approved by the Load control lead before release to Ramp, and if not, "
        "why not?"
    )
    assert (question["section"], question["provenance"], question["severity"]) == (
        "recommendation",
        "",
        None,
    )
    assert [e["label"] for e in question["elements"]] == ["Approve load plan"]
    assert question["evidence"] == [] and question["disposition"] == "open"
    # No finding offers a cause: interpretation needs SME passages, and none explains it.
    assert all(f["section"] == "fact" for f in body["findings"])


def test_no_name_on_the_hidden_list_reaches_the_report(drafted: Drafted) -> None:
    body = run(drafted)
    text = json.dumps(body)
    assert "Priya" not in text and "Nair" not in text
    sent = ga_internal.blocks_for(dset(drafted))[0]["text"]
    assert isinstance(sent, str) and "Priya" not in sent


def test_the_divergence_set_is_the_steps_where_sources_differ(drafted: Drafted) -> None:
    found = dset(drafted)
    assert [(i.ref, i.element.label, i.element.source_state) for i in found.items] == [
        ("d1", "Approve load plan", "documented_only"),
        ("d2", "Resolve or offload", "practiced_only"),
        ("d3", "Load and return LIR", "contested"),
        ("d4", "Deviation in limits?", "contested"),
        ("d5", "Approve deviation", "practiced_only"),
    ]
    d4 = found.items[3]
    assert d4.contested_raci == [("Captain", "A"), ("Load control lead", "A")]
    notes = [s.note for s in d4.sides if s.note]
    assert "Ownership divergence: the Load control lead decides in the SOP, the Captain in " \
        "practice." in notes  # fmt: skip
    # Only the passages behind the stances are sent, each once.
    assert sorted(found.passages) == [f"e{n}" for n in range(1, 9)]


def test_a_map_with_no_differences_gets_an_empty_report_without_ai(
    drafted: Drafted, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = DivergenceSet("v", "e", [], {}, {}, [], [])
    monkeypatch.setattr(ga_internal, "divergence_set", lambda _s, _v: empty)
    body = run(drafted)
    assert body["job"]["status"] == "done" and body["job"]["usage"]["calls"] == 0
    assert body["findings"] == [] and body["questions"] == [] and body["rejected"] == []


# --- The grounding gate --------------------------------------------------------------------------


def finding(**changes: Any) -> ai_schemas.GAFinding:
    base: dict[str, Any] = {
        "finding_type": "threshold_gap",
        "section": "fact",
        "title": "Loading report return: 10 minutes in SOP RP-02, up to 15 minutes in practice",
        "text": "The Ramp Supervisor returns it within 10 minutes; practice waits fifteen minutes.",
        "step_refs": ["d3"],
        "evidence": [
            {"segment_id": "e5", "quote": "within 10 minutes of loading completion"},
            {"segment_id": "e4", "quote": "We sometimes wait fifteen minutes for it"},
        ],
        "basis": "",
        "basis_segment_ids": [],
    }
    return ai_schemas.GAFinding.model_validate({**base, **changes})


def outcome(d: Drafted, **changes: Any) -> tuple[str, str]:
    checked = ga_internal.check(dset(d), finding(**changes))
    return checked.finding.rejection_guardrail, checked.finding.rejection_reason


def test_a_well_grounded_finding_passes(drafted: Drafted) -> None:
    assert outcome(drafted) == ("", "")


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"step_refs": ["d9"]}, ("G3", "refers to a step that isn't in the comparison")),
        ({"step_refs": []}, ("G3", "refers to a step that isn't in the comparison")),
        ({"evidence": []}, ("G3", "cites no passage")),
        (
            {"evidence": [{"segment_id": "e99", "quote": "x"}]},
            ("G3", "cites a passage that wasn't provided"),
        ),
        (
            {"evidence": [{"segment_id": "e5", "quote": "within twenty minutes of the flight"}]},
            ("G4", "quote not found in source"),
        ),
        (
            {"text": "Practice waits 45 minutes."},
            ("G5", "number not found in cited text: 45"),
        ),
        (
            {"text": "The Captain returns the report."},
            ("G5", "role not found in cited text: Captain"),
        ),
        # Only practice quoted, while a document does speak about the step: one-sided.
        (
            {
                "title": "Loading report return waits",
                "text": "Practice waits fifteen minutes.",
                "evidence": [{"segment_id": "e4", "quote": "We sometimes wait fifteen minutes"}],
            },
            ("G3", "no evidence from the documents side"),
        ),
        # A likely cause needs a basis citing what the SMEs said.
        (
            {"section": "interpretation"},
            ("G3", "a pattern or cause needs a basis citing what the SMEs said"),
        ),
        (
            {"section": "interpretation", "basis": "The SOP says so.", "basis_segment_ids": ["e5"]},
            ("G3", "a pattern or cause needs a basis citing what the SMEs said"),
        ),
        (
            {"basis": "x", "basis_segment_ids": ["e99"]},
            ("G3", "the basis cites a passage that wasn't provided"),
        ),
    ],
)
def test_the_gate_rejects(
    drafted: Drafted, changes: dict[str, Any], expected: tuple[str, str]
) -> None:
    assert outcome(drafted, **changes) == expected


def test_a_cause_with_an_sme_basis_is_kept_as_an_inference(drafted: Drafted) -> None:
    checked = ga_internal.check(
        dset(drafted),
        finding(
            section="interpretation",
            title="Container shortages at peak may explain the wait",
            text="The Load controller links the wait to container shortages at peak.",
            basis="The Load controller says they are short of containers at peak.",
            basis_segment_ids=["e4"],
        ),
    )
    assert checked.finding.rejection_guardrail == "" and checked.finding.provenance == "I"


# --- The verifier and failures -------------------------------------------------------------------


def with_verdicts(monkeypatch: pytest.MonkeyPatch, verdicts: dict[str, str]) -> None:
    real = ga_internal._call

    def fake(sessions: Any, ctx: Any, stage_id: str, blocks: Any, model: Any, job_id: Any) -> Any:
        if stage_id != ga_internal.VERIFY_STAGE:
            return real(sessions, ctx, stage_id, blocks, model, job_id)
        answer = [
            {"finding_ref": ref, "verdict": v, "reason": f"{v} for Priya Nair"}
            for ref, v in verdicts.items()
        ]
        return Ok(ai_schemas.GAVerifyOutput.model_validate({"verdicts": answer}))

    monkeypatch.setattr(ga_internal, "_call", fake)


def test_the_verifier_rejects_and_flags(drafted: Drafted, monkeypatch: pytest.MonkeyPatch) -> None:
    # f1 dead control, f2 threshold, f3 ownership, f4 undocumented work (in Claude's order).
    with_verdicts(monkeypatch, {"f1": "supported", "f2": "not_supported", "f3": "partial"})
    body = run(drafted)
    verdicts = {
        f["finding_type"]: (f["verifier_verdict"], f["needs_check"]) for f in body["findings"]
    }
    assert verdicts == {
        "dead_control_candidate": ("supported", False),
        "ownership_mismatch": ("partial", True),
        "undocumented_work": ("partial", True),  # no verdict given: checked by Eric, never assumed
    }
    [rejected] = body["rejected"]
    assert (rejected["finding_type"], rejected["rejection_guardrail"]) == ("threshold_gap", "GAV")
    assert rejected["rejection_reason"] == "not_supported for Load controller"  # names hidden
    assert rejected["severity"] is None
    assert body["analysis"]["counts"] == {"kept": 3, "rejected": 1, "open": 4, "needs_check": 2}


def test_with_the_verifier_off_it_is_skipped(drafted: Drafted) -> None:
    body = {"model": "claude-opus-5-5", "effort": "high", "verifier_enabled": False}
    response = drafted.client.put("/api/settings/model", json=body)
    assert response.status_code == 200, response.text
    body = run(drafted)
    assert body["job"]["stages"][3]["status"] == "skipped"
    assert body["job"]["usage"]["calls"] == 1
    assert {f["verifier_verdict"] for f in body["findings"]} == {"not_run"}


def test_a_failed_call_fails_the_analysis_and_keeps_nothing(
    drafted: Drafted, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ga_internal, "_call", lambda *_a: Err(ErrorKind.IO, "The app couldn't reach Anthropic.")
    )
    body = run(drafted)
    assert body["job"]["status"] == "failed"
    assert body["job"]["error"] == "The app couldn't reach Anthropic."
    assert [s["status"] for s in body["job"]["stages"]][:2] == ["done", "failed"]
    assert body["analysis"]["status"] == "failed"
    assert body["analysis"]["error"] == "The app couldn't reach Anthropic."
    assert body["findings"] == [] and body["questions"] == [] and body["rejected"] == []


# --- Endpoints -----------------------------------------------------------------------------------


def test_list_and_errors(drafted: Drafted) -> None:
    client = drafted.client
    first = run(drafted)["analysis"]
    second = run(drafted)["analysis"]
    listed = client.get(f"/api/versions/{drafted.version_id}/gap-analyses").json()
    assert [a["id"] for a in listed] == [second["id"], first["id"]]  # newest first
    assert client.get("/api/versions/nope/gap-analyses").status_code == 404
    missing = client.post("/api/versions/nope/gap-analyses/internal")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "That version doesn't exist."
    gone = client.get("/api/gap-analyses/nope")
    assert gone.status_code == 404
    assert gone.json()["error"]["message"] == "That gap analysis doesn't exist."


def test_one_analysis_at_a_time_per_version(drafted: Drafted) -> None:
    from app.actions import gap

    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    queued = gap.start_internal(sessions, drafted.version_id, lambda _job: None)
    assert isinstance(queued, Ok)
    again = drafted.client.post(f"/api/versions/{drafted.version_id}/gap-analyses/internal")
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "A gap analysis is already running for this version."
