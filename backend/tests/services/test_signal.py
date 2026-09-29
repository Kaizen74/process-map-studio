"""Signal strength (services/signal.py; P12): from the kinds of a map's sources."""

from __future__ import annotations

import pytest

from app.services.signal import signal_strength


@pytest.mark.parametrize(
    ("kinds", "level", "score"),
    [
        (["interview_transcript", "sop"], "strong", 3),
        (["interview_transcript", "manual", "job_description"], "strong", 3),
        (["interview_transcript", "job_description"], "moderate", 2),
        (["interview_transcript", "executed_artefact"], "moderate", 2),
        (["interview_transcript", "other"], "moderate", 2),
        (["interview_transcript"], "limited", 1),
        (["interview_transcript", "interview_transcript"], "limited", 1),
    ],
)
def test_levels(kinds: list[str], level: str, score: int) -> None:
    signal = signal_strength(kinds)
    assert signal is not None and (signal.level, signal.score) == (level, score)


def test_no_interview_no_signal() -> None:
    assert signal_strength(["sop", "job_description"]) is None
    assert signal_strength([]) is None


def test_limited_says_what_to_do_in_plain_words() -> None:
    signal = signal_strength(["interview_transcript"])
    assert signal is not None and signal.label == "Limited"
    assert "confirm it with a document or another SME" in signal.detail
