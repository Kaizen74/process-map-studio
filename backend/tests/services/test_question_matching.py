"""Question matching (services/question_matching.py; PRD v1.10 §3.12.10 step A, acceptance
criteria 62 and 79): the A.9 matching test, and the same test re-run with the standard templates'
own wording and IDs, as an interviewer would read them from the template."""

from __future__ import annotations

import re

import pytest

from app.domain.enums import InterviewType
from app.services import question_matching as matching
from tests.services.test_question_bank import bank

# PRD v1.10 Appendix A.1: the interviewer's turns in the fixture transcript.
A1_INTERVIEWER = {
    "06:38": "[M2.2] Walk me through the last flight you planned, step by step, as it actually "
    "went.",
    "21:45": "How long did each part take, and where were you waiting on someone or something?",
    "24:40": "[M5.s1] Was that night more like following the procedure, needing an expert, "
    "working it out as you went, or firefighting?",
    "29:40": "[M4.3] How do you decide what to propose when it's outside tolerance? Is there a "
    "rule for this, or does it depend?",
}
# A.9: tagged 06:38 → M2.2, 24:40 → M5.s1, 29:40 → M4.3; untagged, by wording: 21:45 → M2.4.
A9_EXPECTED = {"06:38": ("M2.2", "tag"), "21:45": ("M2.4", "wording"),
               "24:40": ("M5.s1", "tag"), "29:40": ("M4.3", "tag")}  # fmt: skip
# Words an interviewer puts in the [brackets] when reading a template aloud.
FILLED = {
    "[scope]": "load control", "[adjacent functions]": "the ramp team",
    "[other team]": "airline ops", "[list]": "plan, checks, loading, load sheet",
    "[e.g. plan approval by the lead]": "a plan approval by the lead",
    "[step]": "the loading report", "[SME's words]": "a paper chase",
    "[your team]": "load control", "[SME's own words, ≤ 20 words]": "the report often comes late",
    "[role A]": "the load controller", "[role B]": "the ramp lead",
    "[activity]": "loading", "[other role's team]": "the ramp team",
    "[A]": "the plan", "[B]": "the load sheet",
}  # fmt: skip


def practice_questions() -> list:  # type: ignore[type-arg]
    return [bank().question(q) for q in bank().template_ids(InterviewType.PRACTICE)]


def spoken(wording: str) -> str:
    for placeholder, words in FILLED.items():
        wording = wording.replace(placeholder, words)
    assert "[" not in wording, wording
    return wording


def test_a9_the_fixture_interviewer_turns_match_the_default_practice_guide() -> None:
    found = {
        at: (m.question_id, m.method)
        for at, text in A1_INTERVIEWER.items()
        if (m := matching.match_turn(text, practice_questions())) is not None
    }
    assert found == A9_EXPECTED


@pytest.mark.parametrize("kind", list(InterviewType))
@pytest.mark.parametrize("tagged", [True, False], ids=["with ID", "wording only"])
def test_a_transcript_read_from_a_template_matches_every_question(
    kind: InterviewType, tagged: bool
) -> None:
    """Criterion 79: a transcript using the template's wording or IDs is matched to the right
    questions (every question, including the signifiers, whose wording repeats per story)."""
    questions = [bank().question(q) for q in bank().template_ids(kind)]
    wrong = []
    for q in questions:
        if q.id == "M0.1" or q.id == "F6":  # the opener is read from the top; F6 is a slot
            continue
        text = spoken(q.wording)
        turn = f"[{q.id}] {text}" if tagged else text
        match = matching.match_turn(turn, questions)
        if match is None or match.question_id != q.id:
            wrong.append((q.id, match))
        elif not tagged:
            assert match.method == "wording" and match.score >= matching.THRESHOLD
    assert wrong == []


def test_one_ashen_question_at_a_time_is_matched_to_m4_5() -> None:
    match = matching.match_turn("Do you have a rule of thumb?", practice_questions())
    assert match is not None and match.question_id == "M4.5"


@pytest.mark.parametrize(
    "turn",
    [
        "Can you hear me? Yep, can hear you.",
        "Thanks, that's really helpful.",
        "[Z9] Let's take a short break.",
    ],
)
def test_free_conversation_is_left_unmatched(turn: str) -> None:
    assert matching.match_turn(turn, practice_questions()) is None


def test_a_tag_for_a_question_not_in_the_guide_falls_back_to_wording() -> None:
    landscape = [bank().question(q) for q in bank().template_ids(InterviewType.LANDSCAPE)]
    match = matching.match_turn(
        "[M2.4] How long did each part take, and where were you waiting on someone or something?",
        landscape,
    )
    assert match is None or match.method == "wording"


def test_normalise_ignores_punctuation_quotes_and_case() -> None:
    assert matching.normalise(
        "\u201cWhat\u2019s the BUSIEST part?\u201d \u2014 and then\u2026"
    ) == ("what's the busiest part and then")
    assert re.fullmatch(r"[a-z0-9' ]+", matching.normalise(bank().question("M4.5").wording))
