"""Signal strength (services/signal.py; P12): from the kinds of a map's sources."""

from __future__ import annotations

import pytest

from app.services.signal import (
    DOCUMENTS_ONLY,
    DOCUMENTS_QUALITY_WARNING,
    QUALITY_WARNING,
    quality_warning,
    signal_strength,
)


@pytest.mark.parametrize(
    ("kinds", "level", "score"),
    [
        (["interview_transcript", "sop"], "strong", 3),
        (["interview_transcript", "manual", "job_description"], "strong", 3),
        (["interview_transcript", "job_description"], "moderate", 2),
        (["interview_transcript", "executed_artefact"], "moderate", 2),
        (["interview_transcript", "other"], "moderate", 2),
        (["interview_transcript", "working_spreadsheet", "email_thread"], "moderate", 2),
        (["interview_transcript"], "limited", 1),
        (["interview_transcript", "interview_transcript"], "limited", 1),
    ],
)
def test_levels(kinds: list[str], level: str, score: int) -> None:
    signal = signal_strength(kinds)
    assert signal is not None and (signal.level, signal.score) == (level, score)


@pytest.mark.parametrize(
    "kinds",
    [
        ["sop"],
        ["manual", "job_description"],
        ["sop", "sop", "job_description"],
        ["executed_artefact"],
        ["working_spreadsheet", "email_thread"],
        ["other"],
    ],
)
def test_documents_alone_are_limited_and_say_so(kinds: list[str]) -> None:
    """Eric, 2026-10-20: a map drafted from documents alone shows the process as written."""
    signal = signal_strength(kinds)
    assert signal is not None and (signal.level, signal.score) == ("limited", 1)
    assert signal is DOCUMENTS_ONLY and "documents only" in signal.detail
    assert "Confirm it with an interview" in signal.detail


def test_nothing_that_describes_steps_no_signal() -> None:
    """Job descriptions describe roles; a charter states intent and is never drafted from."""
    assert signal_strength(["job_description"]) is None
    assert signal_strength(["policy_or_charter", "job_description"]) is None
    assert signal_strength([]) is None


def test_each_limited_signal_has_its_own_quality_warning() -> None:
    interviews, documents = signal_strength(["interview_transcript"]), signal_strength(["sop"])
    assert interviews is not None and documents is not None
    assert quality_warning(interviews) == QUALITY_WARNING
    assert quality_warning(documents) == DOCUMENTS_QUALITY_WARNING
    assert "interview" in DOCUMENTS_QUALITY_WARNING
    strong = signal_strength(["interview_transcript", "sop"])
    assert strong is not None and quality_warning(strong) is None


def test_limited_says_what_to_do_in_plain_words() -> None:
    signal = signal_strength(["interview_transcript"])
    assert signal is not None and signal.label == "Limited"
    assert "confirm it with a document or another SME" in signal.detail
