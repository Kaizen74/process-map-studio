"""Verbatim-to-workflow translation on the illustrative sample (PRD v1.10 §3.12.10, Appendix A.9),
through the real draft job with Claude mocked."""

from __future__ import annotations

from app.db import session_scope
from app.domain.result import Ok
from app.pipeline import s1_extract
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
