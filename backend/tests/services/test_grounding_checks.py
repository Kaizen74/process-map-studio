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
