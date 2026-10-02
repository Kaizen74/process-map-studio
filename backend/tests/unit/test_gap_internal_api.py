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
        "The documents-vs-practice report is ready: 6 findings, 2 questions for your SMEs, "
        "0 rejected findings."  # A.8 (C4b): + the two reality gaps and the question one raises
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
        # A.8 (C4b): the reality gaps (the severity rule of §3.11.1 names no reality gap: low).
        ("known_adaptation", "low", ["Load and return LIR", "Read report at aircraft"], "O"),
        ("constraint_mismatch", "low", ["Deviation in limits?"], "I"),
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
    assert analysis["counts"] == {"kept": 6, "rejected": 0, "open": 8, "needs_check": 0}
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
        ("practice", "landscape ramp lead", "", "silent"),  # A.10 says nothing of it either
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
    question, why = body["questions"]
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
    # No finding offers a cause: interpretation needs SME passages, and none explains it. The one
    # interpretation is A.8's constraint mismatch, whose basis is the SME's own cue (29:48); no
    # reason was stated for it, so its class is unexplained and it asks why (§3.12.7).
    assert [f["finding_type"] for f in body["findings"] if f["section"] != "fact"] == [
        "constraint_mismatch"
    ]
    assert (why["finding_type"], why["question"], [e["label"] for e in why["elements"]]) == (
        "constraint_mismatch",
        'On "Deviation in limits?": Why do people do it this way?',
        ["Deviation in limits?"],
    )


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
        # v1.10 A.5: the lived busy-wave variation, in practice only (undocumented work).
        ("d4", "Busy wave?", "practiced_only"),
        ("d5", "Read report at aircraft", "practiced_only"),
        ("d6", "Deviation in limits?", "contested"),
        ("d7", "Approve deviation", "practiced_only"),
    ]
    d4 = found.items[5]  # Deviation in limits?
    assert d4.contested_raci == [("Captain", "A"), ("Load control lead", "A")]
    notes = [s.note for s in d4.sides if s.note]
    assert "Ownership divergence: the Load control lead decides in the SOP, the Captain in " \
        "practice." in notes  # fmt: skip
    # Only the passages behind the stances are sent, each once.
    # v1.10: + the 22:30 passage behind the busy-wave steps; A.10 (C3): + the landscape
    # interview's 02:18 passage behind the loading step; C4b: + the 29:48 work-type cue.
    assert sorted(found.passages) == sorted(f"e{n}" for n in range(1, 12))
    assert (d4.work_type, [found.passages[r].segment.anchor for r in d4.work_type_refs]) == (
        "complex", ["29:48"])  # fmt: skip
    # The official and lived accounts of the steps, with the SME's stated reason (A.8).
    lir, reading = found.items[2], found.items[4]
    assert {(a.account_type, found.passages[a.passage_refs[0]].segment.anchor)
            for a in lir.accounts} == {("official", "22:30"), ("lived", "21:50"),
                                       ("lived", "02:18")}  # fmt: skip
    assert [a.stated_reason for a in reading.accounts] == ["otherwise we'd miss the slot"]


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
            {"segment_id": "e6", "quote": "within 10 minutes of loading completion"},
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
            {"evidence": [{"segment_id": "e6", "quote": "within twenty minutes of the flight"}]},
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
            {"section": "interpretation", "basis": "The SOP says so.", "basis_segment_ids": ["e6"]},
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
    # f1 dead control, f2 threshold, f3 ownership, f4 known adaptation, f5 constraint mismatch,
    # f6 undocumented work (in Claude's order).
    with_verdicts(monkeypatch, {"f1": "supported", "f2": "not_supported", "f3": "partial"})
    body = run(drafted)
    verdicts = {
        f["finding_type"]: (f["verifier_verdict"], f["needs_check"]) for f in body["findings"]
    }
    assert verdicts == {
        "dead_control_candidate": ("supported", False),
        "ownership_mismatch": ("partial", True),
        "undocumented_work": ("partial", True),  # no verdict given: checked by Eric, never assumed
        "known_adaptation": ("partial", True),
        "constraint_mismatch": ("partial", True),
    }
    [rejected] = body["rejected"]
    assert (rejected["finding_type"], rejected["rejection_guardrail"]) == ("threshold_gap", "GAV")
    assert rejected["rejection_reason"] == "not_supported for Load controller"  # names hidden
    assert rejected["severity"] is None
    assert body["analysis"]["counts"] == {"kept": 5, "rejected": 1, "open": 7, "needs_check": 4}


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


# --- Reality gaps (§3.12.7; A.8; C4b) ------------------------------------------------------------

OFFICIAL = {
    "segment_id": "e7",
    "quote": "Officially the ramp should send the report within ten minutes",
}
LIVED = {"segment_id": "e7", "quote": "What actually happens on a busy wave is I walk down"}
ADAPTATION: dict[str, Any] = {
    "finding_type": "known_adaptation",
    "title": "Loading report: sent officially, read at the aircraft on a busy wave",
    "text": "Officially the Ramp sends the report; on a busy wave the Load controller reads it.",
    "step_refs": ["d3", "d5"],
    "evidence": [OFFICIAL, LIVED],
}
MISMATCH: dict[str, Any] = {
    "finding_type": "constraint_mismatch",
    "section": "interpretation",
    "title": "A fixed decider in the SOP for a call with no fixed answer",
    "text": "SOP LC-07 sets who decides; the Load controller says there's no fixed answer.",
    "step_refs": ["d6"],
    "evidence": [
        {"segment_id": "e9", "quote": "the Load Control Lead shall decide on corrective action"},
        {"segment_id": "e10", "quote": "There's no fixed answer"},
    ],
    "basis": "The Load controller says there's no fixed answer.",
    "basis_segment_ids": ["e10"],
}


def test_a8_reality_gaps_with_a_class_only_from_a_stated_reason(drafted: Drafted) -> None:
    d = dset(drafted)
    kept = ga_internal.check(d, finding(**ADAPTATION, gap_class="effective_adaptation",
                                        stated_reason="otherwise we'd miss the slot",
                                        cause_type="capacity_mismatch"))  # fmt: skip
    f = kept.finding
    assert f.rejection_reason == "" and f.provenance == "O"
    assert (f.gap_class, f.stated_reason, f.cause_type) == (
        "effective_adaptation", "otherwise we'd miss the slot", "capacity_mismatch")  # fmt: skip
    # Both sides compared are the SME's own accounts: no documents side is needed.
    assert {e.side for e in f.evidence} == {"practice"}
    # A class without a stated reason, or with a reason not in the passages: unexplained.
    guessed = ga_internal.check(d, finding(**ADAPTATION, gap_class="risky_drift")).finding
    assert (guessed.gap_class, guessed.stated_reason, guessed.cause_type) == (
        "unexplained", "", None)  # fmt: skip
    invented = ga_internal.check(d, finding(**ADAPTATION, gap_class="risky_drift",
                                            stated_reason="to save money",
                                            cause_type="policy_control")).finding  # fmt: skip
    assert (invented.gap_class, invented.cause_type) == ("unexplained", None)
    assert invented.notes == [ga_internal.REASON_NOT_FOUND]
    # Every unexplained reality gap raises the bank's M6.4 question about its first step.
    asked = [q.question for q in ga_internal.report(d, [guessed and ga_internal.check(
        d, finding(**ADAPTATION))], []) if q.question]  # fmt: skip
    assert asked == ['On "Load and return LIR": Why do people do it this way?']
    # Other findings never carry a class, whatever the answer says.
    plain = ga_internal.check(d, finding(gap_class="obsolete_rule")).finding
    assert (plain.gap_class, plain.stated_reason, plain.cause_type) == (None, "", None)


def test_a8_constraint_mismatch_needs_complex_work_and_the_prescription(drafted: Drafted) -> None:
    d = dset(drafted)
    kept = ga_internal.check(d, finding(**MISMATCH)).finding
    assert (kept.rejection_reason, kept.gap_class, kept.provenance) == ("", "unexplained", "I")


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        # Load and return LIR alone has no lived account in 22:30 to compare with: quote both.
        ({**ADAPTATION, "step_refs": ["d3"]}, ga_internal.NOT_BOTH_ACCOUNTS),
        ({**ADAPTATION, "step_refs": ["d2"],
          "evidence": [{"segment_id": "e3", "quote": "the airline decides what to offload"}]},
         ga_internal.NO_ACCOUNTS),
        ({**ADAPTATION, "evidence": [OFFICIAL]}, ga_internal.NOT_BOTH_ACCOUNTS),
        # Approve deviation has no work type showing complex work.
        ({**MISMATCH, "step_refs": ["d7"]}, ga_internal.NOT_COMPLEX),
        ({**MISMATCH, "evidence": MISMATCH["evidence"][1:]}, ga_internal.NO_PRESCRIPTION),
    ],
)  # fmt: skip
def test_the_gate_rejects_reality_gaps_that_dont_hold(
    drafted: Drafted, changes: dict[str, Any], expected: str
) -> None:
    assert outcome(drafted, **changes) == ("G3", expected)
