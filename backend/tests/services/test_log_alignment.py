"""R5a: the deterministic first pass and the checks on Claude's suggestions (PRD §3.13.4,
criterion 86; fixture A.11 against the Appendix A sample map)."""

from __future__ import annotations

from app.services.log_alignment import (
    ActivityInfo,
    StepInfo,
    Suggestion,
    check_suggestions,
    propose,
    words,
)

LC, RAMP = "Load controller", "Ramp"
SAMPLE_STEPS = [
    StepInfo("draft-load-plan", "Draft load plan", "activity", LC, ("forward hold",)),
    StepInfo("approve-load-plan", "Approve load plan", "approval", "Load control lead"),
    StepInfo("special-loads-ok", "Special loads OK?", "decision", LC),
    StepInfo("resolve-or-offload", "Resolve or offload", "activity", "Airline ops"),
    StepInfo("load-and-return-lir", "Load and return LIR", "activity", RAMP),
    StepInfo("busy-wave", "Busy wave?", "decision", LC, ("wave",)),
    StepInfo("read-report-at-aircraft", "Read report at aircraft", "activity", LC),
    StepInfo("deviation-in-limits", "Deviation in limits?", "decision", LC),
    StepInfo("approve-deviation", "Approve deviation", "approval", "Captain", ("re-trim",)),
    StepInfo("issue-load-sheet", "Issue load sheet", "activity", LC),
]
A11 = [
    ActivityInfo("Plan created", 200, 200, LC),
    ActivityInfo("Special load checked", 200, 200, LC),
    ActivityInfo("Loading report received", 200, 200, RAMP),
    ActivityInfo("Weight deviation checked", 200, 200, LC),
    ActivityInfo("Load sheet issued", 200, 200, LC),
    ActivityInfo("Plan revised", 40, 40, LC),
    ActivityInfo("Manual weight override", 23, 23, LC),
]


def test_words_ignore_case_endings_and_small_words() -> None:
    assert words("Loading report received") == {"load", "report", "receiv"}
    assert words("Special loads OK?") == {"special", "load"}
    assert words("Issue load sheet") == words("Load sheet issued")
    assert words("Read report at aircraft") == {"read", "report", "aircraft"}


def test_a11_activities_are_proposed_as_appendix_a11_expects() -> None:
    found = {a: m.key for a, m in propose(A11, SAMPLE_STEPS).items()}
    assert found == {
        "Plan created": "draft-load-plan",
        "Special load checked": "special-loads-ok",
        "Loading report received": "load-and-return-lir",  # the role decides over two steps
        "Weight deviation checked": "deviation-in-limits",  # not the Captain's approval
        "Load sheet issued": "issue-load-sheet",
        "Plan revised": "draft-load-plan",  # rework into the step it repeats
    }  # Manual weight override: no step shares its words, a hidden-work candidate


def test_the_reason_names_the_activitys_own_words_and_the_role() -> None:
    matches = propose(A11, SAMPLE_STEPS)
    assert matches["Load sheet issued"].reason == (
        "Same words: load, sheet, issued. Same role: Load controller."
    )
    assert matches["Loading report received"].reason == "Same words: loading. Same role: Ramp."


def test_a_weak_match_without_the_role_is_not_proposed() -> None:
    # "report" is one of two words, and the role differs: 0.5 is not enough.
    assert propose([ActivityInfo("Report printed", role="Finance")], SAMPLE_STEPS) == {}
    # The same words with the step's role are: 0.75.
    found = propose([ActivityInfo("Report printed", role=LC)], SAMPLE_STEPS)
    assert found["Report printed"].key == "read-report-at-aircraft"


def test_glossary_terms_count_as_the_steps_words() -> None:
    activity = [ActivityInfo("Wave started", role=LC)]
    assert propose(activity, SAMPLE_STEPS)["Wave started"].key == "busy-wave"
    without = [StepInfo("busy-wave", "Busy period?", "decision", LC)]
    assert propose(activity, without) == {}


def test_ties_go_to_the_same_role_then_the_earlier_step() -> None:
    steps = [StepInfo("a", "Check order", "activity", "Clerk"),
             StepInfo("b", "Check order", "activity", "Buyer")]  # fmt: skip
    assert propose([ActivityInfo("Order checked", role="Buyer")], steps)["Order checked"].key == "b"
    assert propose([ActivityInfo("Order checked")], steps)["Order checked"].key == "a"


def test_claude_suggestions_must_name_what_exists() -> None:
    sent, keys = ["Manual weight override", "Plan revised"], [s.key for s in SAMPLE_STEPS]
    kept, left_out = check_suggestions(
        [
            Suggestion("Manual weight override", "manual-weight-override", "No such step."),
            Suggestion("Plan approved", "approve-load-plan", "No such activity."),
            Suggestion("Plan revised", "draft-load-plan", "  "),  # no reason
            Suggestion("Manual weight override", "deviation-in-limits", " Handles the deviation. "),
            Suggestion("Manual weight override", "approve-deviation", "A second one."),
        ],
        sent,
        keys,
    )
    assert kept == [Suggestion("Manual weight override", "deviation-in-limits",
                               "Handles the deviation.")]  # fmt: skip
    assert left_out == 4
