"""Emerging themes, checked before they are kept (Appendix E tier 3, §3.12.9 rule 3; C7b):
proposed, never forced."""

from __future__ import annotations

import pytest

from app.domain.sensemaking import ThemeProposal
from app.services import sensemaking

STORIES = {"c1", "c2", "c3"}
GOOD = ThemeProposal(
    theme="Workarounds at peak times",
    claim_ids=["c1", "c2"],
    basis="Both stories describe a workaround when the wave is busy.",
)


def test_a_theme_with_two_stories_is_kept_tidied() -> None:
    kept = sensemaking.check_themes(
        [
            GOOD.model_copy(
                update={
                    "theme": "  Workarounds   at peak times ",
                    "claim_ids": ["c1", "c2", "c2", "x9"],
                }
            )
        ],
        STORIES,
        set(),
        [],
    )
    assert kept == [GOOD]
    broken = GOOD.model_copy(update={"theme": "Workarounds at\npeak times"})
    assert sensemaking.check_themes([broken], STORIES, set(), []) == [GOOD]  # tidied onto one line


@pytest.mark.parametrize(
    "bad",
    [
        GOOD.model_copy(update={"claim_ids": ["c1"]}),  # one story only (kept as a story)
        GOOD.model_copy(update={"claim_ids": ["c1", "x9"]}),  # not a story of this version
        GOOD.model_copy(update={"theme": ""}),
        GOOD.model_copy(update={"theme": "x" * 81}),
        GOOD.model_copy(update={"theme": "Violation of the plan"}),
        GOOD.model_copy(update={"theme": "Priya's shortcuts"}),
        GOOD.model_copy(update={"basis": " "}),
        GOOD.model_copy(update={"basis": "Each story is an error by the crew."}),
    ],
)
def test_a_theme_failing_a_check_is_left_out(bad: ThemeProposal) -> None:
    assert sensemaking.check_themes([bad], STORIES, set(), ["Priya"]) == []


def test_a_theme_already_there_or_repeated_is_not_proposed_again() -> None:
    assert sensemaking.check_themes([GOOD], STORIES, {"workarounds at PEAK times"}, []) == []
    assert sensemaking.check_themes([GOOD, GOOD], STORIES, set(), []) == [GOOD]
