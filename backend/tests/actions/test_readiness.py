"""Readiness rules (API_CONTRACT.md → Readiness): `assess` is pure, so each rule is tested alone."""

from __future__ import annotations

from typing import Any

import pytest

from app.actions.readiness import (
    ADD_DOCUMENT,
    ADD_KEY,
    ADD_TRANSCRIPT,
    NAV_ORDER,
    ONLY_JDS,
    assess,
)
from app.domain.models import Readiness, ReadinessFacts, ReviewProgress, SourceFacts


def source(filename: str, kind: str, status: str = "ready", unmapped: int = 0) -> SourceFacts:
    return SourceFacts(
        id=filename,
        filename=filename,
        kind=kind,
        text_status=status,
        unmapped_speakers=unmapped,
    )


TRANSCRIPT = source("interview_transcript.txt", "interview_transcript")
SOP = source("sop_LC-07.docx", "sop")
JD = source("jd_load_controller.docx", "job_description")


def facts(**changes: Any) -> ReadinessFacts:
    base: dict[str, Any] = {
        "trigger": "Flight scheduled",
        "end_point": "Final load sheet issued",
        "sources": [TRANSCRIPT, SOP],
        "version_count": 0,
        "published": False,
        "latest_progress": ReviewProgress(reviewed=0, total=0),
        "gap_finalised": False,
    }
    return ReadinessFacts(**{**base, **changes})


def check(result: Readiness) -> Readiness:
    """Invariants that hold for every result."""
    assert list(result.nav) == list(NAV_ORDER)
    assert set(result.nav_counts) == {k for k, v in result.nav.items() if v == "attention"}
    assert result.ready_to_draft == (not result.missing)
    assert result.next_step != "gap_analysis"
    return result


def test_brand_new_engagement_starts_at_setup() -> None:
    result = check(assess(facts(trigger="", end_point="", sources=[]), key_set=False))
    assert result.nav == dict.fromkeys(NAV_ORDER, "not_started")
    assert result.next_step == "setup"
    assert result.missing == [ADD_KEY, ADD_TRANSCRIPT, ADD_DOCUMENT]
    assert not (result.transcripts_ready or result.documents_ready or result.draft_exists)


@pytest.mark.parametrize(("trigger", "end_point"), [("x", ""), ("", "x"), ("  ", " ")])
def test_setup_needs_trigger_and_end_point(trigger: str, end_point: str) -> None:
    result = check(assess(facts(trigger=trigger, end_point=end_point), key_set=True))
    assert result.nav["setup"] == "not_started" and result.next_step == "setup"


def test_ready_to_draft_with_key_transcript_and_document() -> None:
    result = check(assess(facts(), key_set=True))
    assert result.ready_to_draft and result.missing == []
    assert result.transcripts_ready and result.documents_ready
    assert (result.nav["setup"], result.nav["sources"]) == ("done", "done")
    assert result.next_step == "draft"


def test_missing_key_is_listed_but_does_not_affect_sources() -> None:
    result = check(assess(facts(), key_set=False))
    assert result.missing == [ADD_KEY]
    assert result.nav["sources"] == "done" and result.next_step == "draft"


def test_only_documents_asks_for_a_transcript() -> None:
    result = check(assess(facts(sources=[SOP]), key_set=True))
    assert result.missing == [ADD_TRANSCRIPT]
    assert result.nav["sources"] == "attention" and result.nav_counts == {"sources": 1}
    assert result.next_step == "sources"


def test_job_descriptions_alone_are_not_a_process_document() -> None:
    result = check(assess(facts(sources=[TRANSCRIPT, JD]), key_set=True))
    assert not result.documents_ready
    assert result.missing == [ONLY_JDS]


@pytest.mark.parametrize("kind", ["sop", "manual", "executed_artefact", "other"])
def test_process_document_kinds(kind: str) -> None:
    result = assess(facts(sources=[TRANSCRIPT, source("doc", kind)]), key_set=True)
    assert result.documents_ready


def test_waiting_transcript_is_named() -> None:
    pending = source("interview.vtt", "interview_transcript", status="pending")
    result = check(assess(facts(sources=[pending, SOP]), key_set=True))
    assert result.missing == ["Wait for the interview transcript to be read (interview.vtt)"]
    assert result.nav_counts == {"sources": 1}


def test_failed_transcript_is_named_once() -> None:
    failed = source("broken.txt", "interview_transcript", status="failed")
    result = check(assess(facts(sources=[failed, SOP]), key_set=True))
    assert result.missing == [
        "The interview transcript couldn't be read (broken.txt). Remove it and upload a new copy"
    ]
    assert result.nav_counts == {"sources": 1}


def test_failed_extra_file_needs_attention_but_does_not_block_the_draft() -> None:
    failed = source("old_manual.pdf", "manual", status="failed")
    result = check(assess(facts(sources=[TRANSCRIPT, SOP, failed]), key_set=True))
    assert result.ready_to_draft
    assert result.nav["sources"] == "attention" and result.nav_counts == {"sources": 1}
    assert result.next_step == "sources"


def test_unmapped_speakers_are_listed_per_transcript() -> None:
    one = source("interview_transcript.txt", "interview_transcript", unmapped=1)
    two = source("second.vtt", "interview_transcript", unmapped=2)
    result = check(assess(facts(sources=[one, two, SOP]), key_set=True))
    assert result.speakers_unmapped == 3
    assert result.missing == [
        "Map 1 speaker in interview_transcript.txt",
        "Map 2 speakers in second.vtt",
    ]
    assert result.nav_counts == {"sources": 2}


def test_draft_opens_review_with_a_count() -> None:
    progress = ReviewProgress(reviewed=4, total=10)
    result = check(assess(facts(version_count=1, latest_progress=progress), key_set=True))
    assert result.draft_exists
    assert (result.nav["draft"], result.nav["matrix"], result.nav["registers"]) == ("done",) * 3
    assert result.nav["review"] == "attention" and result.nav_counts == {"review": 6}
    assert result.next_step == "review"


def test_empty_draft_leaves_review_not_started() -> None:
    result = check(assess(facts(version_count=1), key_set=True))
    assert result.nav["review"] == "not_started" and result.next_step == "review"


def test_reviewed_draft_points_to_publishing() -> None:
    progress = ReviewProgress(reviewed=10, total=10)
    result = check(assess(facts(version_count=1, latest_progress=progress), key_set=True))
    assert result.nav["review"] == "done" and result.next_step == "published"


def test_published_version_points_to_exports() -> None:
    progress = ReviewProgress(reviewed=10, total=10)
    result = check(
        assess(facts(version_count=1, latest_progress=progress, published=True), key_set=True)
    )
    assert (result.nav["published"], result.nav["leadership"]) == ("done", "done")
    assert result.next_step == "exports"


def test_gap_analysis_is_never_next_and_can_be_done() -> None:
    result = check(assess(facts(gap_finalised=True), key_set=True))
    assert result.nav["gap_analysis"] == "done"
    fresh = check(assess(facts(), key_set=True))
    assert fresh.nav["gap_analysis"] == "not_started" and fresh.next_step == "draft"
