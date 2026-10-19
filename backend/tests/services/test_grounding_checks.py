"""Grounding checks G3-G5 (PRD §3.8), table-driven on the Appendix A passages and trap shapes."""

from __future__ import annotations

import pytest

from app.services import grounding

# PRD Appendix A passages
S_0640 = (
    "First thing, I build the preliminary load plan off the booked figures, usually around "
    "T-120. Takes me about twenty minutes."
)
S_2150 = (
    "Ramp loads the aircraft, forty minutes or so, and sends back the loading report. It\u2019s "
    "still on paper and I re-key it. We sometimes wait fifteen minutes for it, and at peak "
    "we\u2019re short of containers."
)
SOP_32 = (
    "§3.2 The preliminary load plan shall be approved by the Load Control Lead before release "
    "to Ramp."
)
SOP_4 = "§4 Special loads shall be checked against the acceptance checklist before loading."


def test_normalise_text() -> None:
    assert (
        grounding.normalise_text("  It\u2019s  STILL on-paper, \u201creally\u201d.")
        == "its still on paper really"
    )
    assert grounding.normalise_text("") == ""


# --- G3 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cited", "passed", "reason"),
    [
        (["p2"], True, ""),
        (["p2", "p3"], True, ""),
        (["p9"], False, "cites a passage that wasn't provided"),  # trap T1
        (["p2", "p9"], False, "cites a passage that wasn't provided"),
        ([], False, "cites no passage"),
    ],
)
def test_segments_must_exist_in_the_same_call(cited: list[str], passed: bool, reason: str) -> None:
    result = grounding.verify_segments(cited, {"p1", "p2", "p3"})
    assert (result.passed, result.reason) == (passed, reason)
    assert result.guardrail == ("" if passed else "G3")


# --- G4 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("quote", "cited", "passed"),
    [
        ("I build the preliminary load plan off the booked figures", S_0640, True),
        (
            "i build the PRELIMINARY load plan, off the booked figures.",
            S_0640,
            True,
        ),  # case, punctuation
        ("It's still on paper and I re-key it", S_2150, True),  # straight vs curly apostrophe
        ("I build the prelimnary load plan off the booked figures", S_0640, True),  # one typo
        ("Controller checks fuel figures", S_0640, False),  # trap T2
        ("Checks follow IATA DGR section 9", SOP_4, False),  # trap T5: outside knowledge
        ("Special loads are always accepted without checks", SOP_4, False),  # different meaning
        ("", S_0640, False),
    ],
)
def test_quotes_must_be_found_in_the_cited_text(quote: str, cited: str, passed: bool) -> None:
    result = grounding.verify_quote(quote, cited)
    assert result.passed is passed
    if not passed:
        assert (result.guardrail, result.reason) == ("G4", "quote not found in source")


# Found by the deep review (2026-10-19): character similarity alone let a long quote reverse the
# source's meaning, because one inserted word changes few characters. A quote may differ from
# the source only in spelling and in filler words; it may not add, swap or drop a word that
# carries meaning, and it may never gain or lose a negation.
LONG = (
    "After the weights come in the load controller checks the special loads against the "
    "airline rules and the lead approves the final load plan before it is released to the ramp "
    "team for loading"
)
SPOKEN = "So um the lead you know approves the final load plan before it's released to the ramp."


@pytest.mark.parametrize(
    ("quote", "cited"),
    [
        ("the lead does not approve the final load plan before it is released to the ramp", LONG),
        ("the lead never approves the final load plan before it is released to the ramp team",
         LONG),
        ("the load controller checks the special loads against the airline rules and the ramp "
         "approves the final load plan", LONG),  # a different role
        ("checks the special loads against the airline rules and the lead approves the final "
         "load plan after it is released to the ramp team", LONG),  # before becomes after
        ("the lead approves the final load plan before it is released to the ramp team "
         "without loading", LONG),  # a word added
        ("Special loads shall not be checked against the acceptance checklist before loading",
         SOP_4),  # a negation added to a document
        ("The preliminary load plan shall be approved by the Load Control Lead before release",
         SOP_32.replace("shall be approved", "shall not be approved")),  # a negation dropped
        ("the lead couldn't release the final load plan before the weights come in and the "
         "ramp team is told", "the lead could release the final load plan before the weights "
         "come in and the ramp team is told"),  # spelled close, opposite meaning
        ("the load controller checks the special loads against the airline rules and the lead "
         "always approves the final load plan", LONG),  # a meaningful word added
        ("the lead approves the final load plan before it is released to the ramp team",
         "Then the lead only approves the final load plan before it is released to the ramp "
         "team for loading"),  # a meaningful word left out (an excerpt may start anywhere)
    ],
)  # fmt: skip
def test_a_quote_that_changes_the_meaning_is_refused(quote: str, cited: str) -> None:
    result = grounding.verify_quote(quote, cited)
    assert (result.passed, result.guardrail) == (False, "G4"), quote


@pytest.mark.parametrize(
    "quote",
    [
        "the lead aproves the final load plan before it is released to the ramp team",  # typo
        "the lead approves the final load plan before its released to the ramp team",
        "the lead approves the final load plan before it's released to the ramp team",
        # "the" left out:
        "the lead approves final load plan before it is released to the ramp team",
    ],
)
def test_spelling_and_small_words_may_still_differ(quote: str) -> None:
    assert grounding.verify_quote(quote, LONG).passed, quote


def test_fillers_in_speech_may_be_left_out() -> None:
    """Claude tidies spoken hesitations when it quotes an interview; that changes no meaning."""
    quote = "So the lead approves the final load plan before it's released to the ramp."
    assert grounding.verify_quote(quote, SPOKEN).passed


def test_a_quote_can_span_two_cited_passages() -> None:
    joined = f"{SOP_32}\n{SOP_4}"
    assert grounding.verify_quote("before release to Ramp. §4 Special loads shall", joined).passed


def test_quotes_over_40_words_are_refused() -> None:
    long_quote = " ".join(["plan"] * 41)
    result = grounding.verify_quote(long_quote, " ".join(["plan"] * 50))
    assert (result.passed, result.reason) == (False, "quote longer than 40 words")


def test_the_quote_threshold_is_adjustable() -> None:
    near = "I build the preliminary load plans off the booked figure"
    assert grounding.verify_quote(near, S_0640).passed
    assert not grounding.verify_quote(near, S_0640, threshold=0.999).passed


# --- G5 numbers ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Takes about twenty minutes", {"20"}),
        ("fifteen to forty minutes", {"15", "40"}),
        ("twenty-five or thirty five", {"25", "35"}),
        ("by T-90, around T - 120", {"T-90", "T-120"}),
        ("10% deviation, 1,5 kg or 1.5 kg", {"10", "1.5"}),
        ("at 06:40", {"6", "40"}),
        ("§3.1 and 007", {"3.1", "7"}),
        ("no numbers here", set()),
    ],
)
def test_numbers_in(text: str, expected: set[str]) -> None:
    assert grounding.numbers_in(text) == expected


@pytest.mark.parametrize(
    ("claim", "cited", "passed", "reason"),
    [
        ("Draft load plan takes 20 min", S_0640, True, ""),
        ("Plan drafted around T-120", S_0640, True, ""),
        ("Plan takes 30 min", S_0640, False, "number not found in cited text: 30"),  # trap T3
        ("Plan ready by T-90", S_0640, False, "number not found in cited text: T-90"),
        ("Plan ready 120 min before", S_0640, False, "number not found in cited text: 120"),
        ("Loading takes 40 minutes; wait up to 15 minutes", S_2150, True, ""),
        ("Report returned within 10 minutes", S_2150, False, "number not found in cited text: 10"),
        ("No figures in this claim", S_0640, True, ""),
    ],
)
def test_numbers_must_be_in_the_cited_text(
    claim: str, cited: str, passed: bool, reason: str
) -> None:
    result = grounding.verify_numbers(claim, cited)
    assert (result.passed, result.reason) == (passed, reason)
    assert result.guardrail == ("" if passed else "G5")


@pytest.mark.parametrize(
    ("basis", "passed"),
    [
        ("40 minutes of loading plus a wait of up to 15 minutes gives up to 55 minutes", True),
        ("", False),  # an observed claim can't add a number
        ("probably 55 minutes", False),  # the basis must derive it from the cited numbers
        ("forty plus fifteen", False),  # the derived number itself must appear in the basis
    ],
)
def test_inferred_numbers_need_a_derivation_from_cited_numbers(basis: str, passed: bool) -> None:
    result = grounding.verify_numbers("Loading and waiting take up to 55 minutes", S_2150, basis)
    assert result.passed is passed


# --- G5 roles ------------------------------------------------------------------------------------

KNOWN = [["Load controller", "LC"], ["Load control lead"], ["Ramp agent", "Ramp"]]


@pytest.mark.parametrize(
    ("roles", "cited", "passed", "reason"),
    [
        (["Load Control Lead"], SOP_32, True, ""),
        (["load control lead"], SOP_32, True, ""),
        (["Duty manager"], SOP_32, False, "role not found in cited text: Duty manager"),  # trap T4
        (["Ramp agent"], S_2150, True, ""),  # "Ramp" is a confirmed alias
        (["Load controller"], "Load controller: I build the plan.", True, ""),  # speaker role
        (["Load controller"], "The LC prepares the plan.", True, ""),  # alias in the text
        (["Load controller"], "Load controllers prepare plans.", True, ""),  # plural
        (["Load controller"], SOP_4, False, "role not found in cited text: Load controller"),
        (["Captain"], "the captain who decides", True, ""),
        (["", "  "], SOP_4, True, ""),
    ],
)
def test_roles_must_be_in_the_cited_text(
    roles: list[str], cited: str, passed: bool, reason: str
) -> None:
    result = grounding.verify_roles(roles, cited, KNOWN)
    assert (result.passed, result.reason) == (passed, reason)


def test_an_alias_only_counts_when_eric_confirmed_it() -> None:
    assert not grounding.verify_roles(["Load controller"], "The LC prepares the plan.").passed
