"""Questions and merge decisions (API_CONTRACT.md → Review; PRD §5.7.10, §9 assumption 8).

The illustrative sample has one merge made while drafting: "Load and return LIR" joins S2's
"Load aircraft" (interview) and "Return loading report" (SOP RP-02) at 0.86."""

from __future__ import annotations

from typing import Any

from app.db import session_scope
from app.domain.graph import MergeProposalRecord
from app.repositories import elements as map_repo
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_add import graph, lines, lint_rules
from tests.unit.test_review_edit import element

__all__ = ["drafted"]


def proposals(d: Drafted) -> list[dict[str, Any]]:
    response = d.client.get(f"/api/versions/{d.version_id}/merge-proposals")
    assert response.status_code == 200, response.text
    return list(response.json())


def decide(d: Drafted, proposal: str, decision: str) -> Any:
    return d.client.post(f"/api/merge-proposals/{proposal}/decision", json={"decision": decision})


def labels(d: Drafted) -> list[str]:
    return [e["label"] for e in graph(d)["elements"]]


def test_the_merge_made_while_drafting_is_listed_side_by_side(drafted: Drafted) -> None:
    [p] = proposals(drafted)
    assert (p["proposed_label"], p["similarity"], p["decision"]) == (
        "Load and return LIR", 0.86, "accepted")  # fmt: skip
    assert p["element_id"] == drafted.ids["Load and return LIR"]
    assert [(g["label"], g["kind"], g["lane_role_name"], g["element_id"]) for g in p["groups"]] == [
        ("Load aircraft", "activity", "Ramp", None),
        ("Return loading report", "activity", "Ramp", None),
    ]
    first, second = p["groups"]
    assert len(first["claims"]) == 5 and len(second["claims"]) == 1  # v1.10: + the official account
    claim = second["claims"][0]
    assert (claim["source_name"], claim["anchor"]) == ("sop_RP-02.docx", "§2")
    assert claim["quote"].startswith("The Ramp Supervisor shall return the loading report")
    assert "Priya" not in str(proposals(drafted))


def test_split_puts_back_the_steps_as_drafted_and_accept_joins_them_again(
    drafted: Drafted,
) -> None:
    [p] = proposals(drafted)
    split = decide(drafted, p["id"], "split")
    assert split.status_code == 200, split.text
    assert split.json()["decision"] == "split" and split.json()["element_id"] is None
    assert "Load and return LIR" not in labels(drafted)
    assert {"Load aircraft", "Return loading report"} <= set(labels(drafted))
    flow = lines(drafted)
    assert {("Special loads OK?", "Load aircraft", "yes", "Yes"),
            ("Load aircraft", "Return loading report", "sequence", ""),
            ("Return loading report", "Deviation in limits?", "sequence", ""),
            ("Approve deviation", "Load aircraft", "rework", "Re-trim")} <= flow  # fmt: skip
    aircraft = element(drafted, "Load and return LIR")  # the same step, now "Load aircraft"
    report_id = next(e["id"] for e in graph(drafted)["elements"]
                     if e["label"] == "Return loading report")  # fmt: skip
    report = drafted.client.get(f"/api/elements/{report_id}").json()
    assert aircraft["label"] == "Load aircraft"
    assert (aircraft["needs_check"], aircraft["confidence"]) == (True, None)
    assert (report["needs_check"], report["confidence"], report["review_status"]) == (
        True, None, "draft")  # fmt: skip
    # Each step's evidence is what its own claims cite, supporting it (the stances were judged
    # against the joined step): the interview for loading, the SOP for the report.
    cited = [(c["source_name"], c["stance"]) for c in report["evidence"] if c["segment_id"]]
    assert cited == [("sop_RP-02.docx", "supports")]
    assert report["source_state"] == "documented_only"
    assert (aircraft["source_state"], aircraft["divergence_types"]) == ("practiced_only", [])
    assert [(r["role_name"], r["letter"]) for r in report["raci"]] == [("Ramp", "R"), ("Ramp", "A")]
    assert lint_rules(drafted) == []
    assert drafted.audit()[0]["action"] == "Split merged step"

    joined = decide(drafted, p["id"], "accepted").json()
    assert joined["decision"] == "accepted"
    assert joined["element_id"] == drafted.ids["Load and return LIR"]
    assert "Return loading report" not in labels(drafted)
    back = element(drafted, "Load and return LIR")
    # Both sources support the joined step; the threshold divergence between them is Claude's
    # comparison (S3), which the next refresh works out again. Until then it needs a check.
    assert back["label"] == "Load and return LIR" and back["source_state"] == "corroborated"
    assert back["needs_check"] and back["confidence"] is None
    flow = lines(drafted)
    assert not any(a == b for a, b, _, _ in flow)  # no line from a step to itself
    assert ("Load and return LIR", "Deviation in limits?", "sequence", "") in flow
    assert lint_rules(drafted) == []


def test_merges_and_splits_leave_reviewed_steps_alone(drafted: Drafted) -> None:
    [p] = proposals(drafted)
    assert decide(drafted, p["id"], "rejected").json()["error"]["message"] == (
        "These steps are merged. Use Split to separate them again."
    )
    drafted.act("Load and return LIR", "confirm")
    refused = decide(drafted, p["id"], "split")
    assert refused.status_code == 409
    assert refused.json()["error"]["message"].startswith("One of these steps has already been")
    assert "Load and return LIR" in labels(drafted)
    assert proposals(drafted)[0]["decision"] == "accepted"


def test_a_pending_proposal_can_be_kept_separate_or_accepted(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        claims = map_repo.element_claims(session, drafted.version_id)
        ids = claims[drafted.ids["Draft load plan"]] + claims[drafted.ids["Issue load sheet"]]
        [pending] = map_repo.add_merge_proposals(
            session,
            drafted.version_id,
            [MergeProposalRecord(claim_ids=ids, proposed_label="Plan and issue", similarity=0.5)],
        )
    [_, p] = proposals(drafted)
    assert p["decision"] == "pending" and p["element_id"] is None
    assert {g["element_id"] for g in p["groups"]} == {
        drafted.ids["Draft load plan"], drafted.ids["Issue load sheet"]}  # fmt: skip
    kept = decide(drafted, pending.id, "rejected").json()
    assert kept["decision"] == "rejected" and len(labels(drafted)) == 10
    merged = decide(drafted, pending.id, "accepted").json()
    assert merged["element_id"] == drafted.ids["Draft load plan"]
    assert "Issue load sheet" not in labels(drafted) and "Plan and issue" in labels(drafted)
    names = {e["id"]: e["label"] for e in graph(drafted)["elements"]}
    questions = drafted.client.get(f"/api/versions/{drafted.version_id}/questions").json()
    assert all(q["element_id"] in names or q["element_id"] is None for q in questions)
    assert ("Plan and issue", "Final load sheet issued", "sequence", "") in lines(drafted)
    assert [r["action"] for r in drafted.audit()[:2]] == ["Accepted merge", "Kept steps separate"]


def test_decision_errors(drafted: Drafted) -> None:
    [p] = proposals(drafted)
    assert decide(drafted, p["id"], "maybe").status_code == 422
    assert decide(drafted, "nope", "accepted").json()["error"]["message"] == (
        "That merge proposal doesn't exist."
    )
    again = decide(drafted, p["id"], "accepted")  # the same decision again changes nothing
    assert again.status_code == 200 and drafted.audit() == []


def test_questions_can_be_marked_answered_and_reopened(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/questions"
    listed = drafted.client.get(url).json()
    assert [(q["reason"], q["element_label"], q["phase_name"]) for q in listed] == [
        ("documented_only", "Approve load plan", "Plan"),
        ("contested", "Load and return LIR", "Check and load"),
        ("contested", "Deviation in limits?", "Close out"),
        ("gap", "", ""),
        ("gap", "", ""),
    ]
    assert all(q["status"] == "open" for q in listed)
    first = listed[0]["id"]
    answered = drafted.client.patch(f"/api/questions/{first}", json={"status": "answered"})
    assert answered.json()["status"] == "answered"
    reopened = drafted.client.patch(f"/api/questions/{first}", json={"status": "open"}).json()
    assert reopened["status"] == "open"
    assert [r["action"] for r in drafted.audit()] == [
        "Reopened question",
        "Marked question answered",
    ]
    bad = drafted.client.patch(f"/api/questions/{first}", json={"status": "later"})
    assert bad.status_code == 422
    assert drafted.client.patch("/api/questions/nope", json={"status": "open"}).status_code == 404
    assert drafted.client.get("/api/versions/nope/questions").status_code == 404
