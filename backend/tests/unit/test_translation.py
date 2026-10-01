"""Verbatim-to-workflow translation on the illustrative sample (PRD v1.10 §3.12.10, Appendix A.9),
through the real draft job with Claude mocked."""

from __future__ import annotations

import json
from typing import Any

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.models import ClaimRecord
from app.domain.result import Ok
from app.pipeline import s1_extract
from app.repositories import claims as claims_repo
from app.services import translation
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]
TRANSCRIPT = "interview_transcript.txt"


def transcript_id(d: Drafted) -> str:
    sources = d.client.get(f"/api/engagements/{d.engagement_id}/sources").json()
    return str(next(s["id"] for s in sources if s["filename"] == TRANSCRIPT))


def test_a9_question_matches_and_answer_blocks_after_a_draft(drafted: Drafted) -> None:
    """Step A (acceptance criterion 62): tagged 06:38 → M2.2, 24:40 → M5.s1, 29:40 → M4.3;
    untagged 21:45 → M2.4 by wording; each SME turn carries its answer block's question."""
    page = drafted.client.get(f"/api/sources/{transcript_id(drafted)}/segments").json()
    assert [(s["anchor"], s["question_id"]) for s in page["segments"]] == [
        ("06:38", "M2.2"), ("06:40", "M2.2"), ("07:55", "M2.2"), ("14:05", "M2.2"),
        ("16:22", "M2.2"), ("21:45", "M2.4"), ("21:50", "M2.4"), ("22:30", "M2.4"),
        ("24:10", "M2.4"), ("24:40", "M5.s1"), ("24:46", "M5.s1"), ("27:15", "M5.s1"),
        ("29:02", "M5.s1"), ("29:40", "M4.3"), ("29:48", "M4.3"), ("31:10", "M4.3"),
    ]  # fmt: skip
    documents = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/sources").json()
    sop = next(s["id"] for s in documents if s["filename"] == "sop_LC-07.docx")
    sop_page = drafted.client.get(f"/api/sources/{sop}/segments").json()
    assert {s["question_id"] for s in sop_page["segments"]} == {None}


def test_s1_receives_question_answer_blocks_targets_and_marker_hints(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        result = s1_extract.prepare(session, transcript_id(drafted))
    assert isinstance(result, Ok)
    prepared = result.value
    assert sorted(prepared.questions) == ["M2.2", "M2.4", "M4.3", "M5.s1"]
    first, second, _third = s1_extract.chunks_for(prepared.info.kind, prepared.segments)
    [block] = s1_extract.blocks_for(prepared.info.kind, first, prepared.questions)
    text = str(block["text"])
    # The question list comes first, with each question's targets (what it is evidence for).
    assert text.startswith("<questions>")
    assert (
        '<question id="M2.2" movement="M2" targets="Flow (lived sequence, roles, handoffs' in text
    )
    # Each turn carries its block's question; the SME's turns carry the marker hints.
    assert 'anchor="06:38" speaker="Interviewer" question="M2.2">[M2.2] Walk me through' in text
    assert (
        'anchor="06:40" speaker="Load controller" question="M2.2" '
        'markers="explicit_order: First thing; variation: usually; explicit_order: around T-">'
    ) in text
    # Names stay hidden in what is sent (G10).
    assert "Priya" not in text
    [later] = s1_extract.blocks_for(prepared.info.kind, second, prepared.questions)
    assert 'markers="account_official: Officially; ' in str(later["text"])
    assert "account_lived: What actually happens" in str(later["text"])


# --- B3: accounts, stated reasons, variations and marker reviews (§3.12.3; A.8; crit. 51, 63) -


def claims_at(d: Drafted) -> dict[str, list[ClaimRecord]]:
    """The version's verified interview claims by the anchor of the passage they cite."""
    sessions = d.client.app.state.sessions  # type: ignore[attr-defined]
    page = d.client.get(f"/api/sources/{transcript_id(d)}/segments").json()["segments"]
    anchors = {s["id"]: s["anchor"] for s in page}
    out: dict[str, list[ClaimRecord]] = {}
    with session_scope(sessions) as session:
        for c in claims_repo.list_claims(session, d.version_id, "verified"):
            if c.account_type is not None:
                out.setdefault(anchors[c.segment_ids[0]], []).append(c)
    return out


def test_a8_account_tags_with_quoted_cues(drafted: Drafted) -> None:
    by_anchor = claims_at(drafted)
    official, lived = by_anchor["22:30"]
    assert (official.account_type, official.payload["account_cue"]) == ("official", "Officially")
    assert (lived.account_type, lived.payload["account_cue"]) == ("lived", "What actually happens")
    # The lived account keeps the SME's stated reason and the condition of the variation.
    assert lived.payload["stated_reason"] == "otherwise we'd miss the slot"
    assert lived.payload["variation_condition"] == "on a busy wave"
    assert {c.account_type for c in by_anchor["21:50"]} >= {"lived"}
    # Every interview claim carries an account; documents' claims carry none.
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        verified = claims_repo.list_claims(session, drafted.version_id, "verified")
    interview_source = transcript_id(drafted)
    assert all((c.account_type is not None) == (c.source_id == interview_source) for c in verified)


def test_marker_hints_are_confirmed_or_set_aside_with_a_quote(drafted: Drafted) -> None:
    [plan] = [c for c in claims_at(drafted)["06:40"]]
    assert plan.payload["markers"] == [
        {"marker": "explicit_order: First thing", "confirmed": True, "quote": "First thing"},
        {"marker": "variation: usually", "confirmed": False, "quote": "usually around T-120"},
    ]
    assert plan.payload["markers_dropped"] == 0


def element_named(d: Drafted, label: str) -> dict[str, Any]:
    graph = d.client.get(f"/api/versions/{d.version_id}/graph").json()
    element = next(e for e in graph["elements"] if e["label"] == label)
    return dict(d.client.get(f"/api/elements/{element['id']}").json())


def test_each_step_shows_its_accounts_and_the_questions_behind_its_answers(
    drafted: Drafted,
) -> None:
    lir = element_named(drafted, "Load and return LIR")
    assert lir["account_summary"] == {"official": 1, "lived": 3, "unclear": 1}
    assert lir["practice_described"] is True
    official = next(a for a in lir["answers"] if a["account_type"] == "official")
    assert official == {
        "quote": "Officially the ramp should send the report within ten minutes.",
        "account_type": "official",
        "account_cue": "Officially",
        "stated_reason": "",
        "variation_condition": "",
        "source_id": transcript_id(drafted),
        "segment_id": official["segment_id"],
        "anchor": "22:30",
        "question_id": "M2.4",
        "question": "How long did each part take, and where were you waiting on someone or "
        "something?",
    }
    # A step only the documents describe has no account; the interview is silent on it.
    approve = element_named(drafted, "Approve load plan")
    assert approve["account_summary"] == {"official": 0, "lived": 0, "unclear": 0}
    assert approve["practice_described"] is None and approve["answers"] == []
    # Names stay hidden in the answers (G10).
    assert "Priya" not in json.dumps(lir)


def test_practice_not_described_when_only_the_official_account_speaks() -> None:
    summary = translation.account_summary(["official", "unclear", None])
    assert summary.model_dump() == {"official": 1, "lived": 0, "unclear": 1}
    assert translation.practice_described(summary) is False
    assert translation.practice_described(translation.account_summary(["lived"])) is True
    assert translation.practice_described(translation.account_summary([None, "unclear"])) is None


def test_ungrounded_cues_reasons_conditions_and_marker_quotes_are_dropped() -> None:
    cited = "Load controller: Officially the ramp should send the report within ten minutes."
    claim = ai_schemas.S1InterviewClaim(
        claim_type="threshold",
        text="The Ramp should send the report within ten minutes.",
        responsible_role="Ramp",
        accountable_role="",
        decider_role="",
        mechanism="none",
        duration_text="",
        threshold="",
        segment_ids=["p8"],
        quote="Officially the ramp should send the report within ten minutes.",
        provenance="O",
        basis="",
        account_type="lived",
        account_cue="What actually happens",  # not in the cited passage
        stated_reason="because the SOP is old",  # invented
        variation_condition="officially",  # in the passage: kept
        markers=[
            ai_schemas.S1MarkerReview(
                marker="account_official: Officially", confirmed=True, quote="Officially"
            ),
            ai_schemas.S1MarkerReview(marker="wait: wait", confirmed=True, quote="we wait"),
        ],
    )
    account, fields = s1_extract.check_interview_fields(claim, cited)
    assert account == "unclear"
    assert fields["account_cue"] == "" and fields["account_cue_dropped"] is True
    assert fields["stated_reason"] == "" and fields["variation_condition"] == "officially"
    assert fields["markers"] == [
        {"marker": "account_official: Officially", "confirmed": True, "quote": "Officially"}
    ]
    assert fields["markers_dropped"] == 1
