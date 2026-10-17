"""The variants service (R8): a variant's path through Eric's matches, its fit with a view and
the steps around a hidden activity. Pure, no database."""

from __future__ import annotations

from app.services import system_variants as v

LABELS = {"a": "Draft plan", "b": "Check loads", "c": "Issue sheet"}
DONE = v.ViewMap("done", {"a": "Draft plan", "b": "Check loads", "c": "Issue sheet"},
                 [("a", "b"), ("b", "c")])  # fmt: skip


def test_a_path_follows_the_decisions() -> None:
    steps = v.path(["Opened", "Override", "Phone"], {"Opened": "a"}, {"Override"})
    assert [(s.key, s.status) for s in steps] == [
        ("a", "matched"), (None, "hidden_work"), (None, "not_matched")]  # fmt: skip


def test_a_variant_fits_when_the_view_leads_from_each_step_to_the_next() -> None:
    steps = v.path(["x", "y", "y2", "z"], {"x": "a", "y": "b", "y2": "b", "z": "c"}, set())
    assert v.fit(steps, DONE, LABELS) == (True, [])  # b repeated straight after itself: once


def test_what_does_not_fit_is_said_in_words() -> None:
    documented = v.ViewMap("documented", {"a": "Draft plan", "c": "Issue sheet"}, [("a", "c")])
    steps = v.path(["x", "y", "z"], {"x": "a", "y": "b", "z": "c"}, set())
    assert v.fit(steps, documented, LABELS) == (
        False, ["Check loads isn't in the As documented view."])  # fmt: skip
    backwards = v.path(["z", "x"], {"x": "a", "z": "c"}, set())
    assert v.fit(backwards, DONE, LABELS) == (
        False, ["The As done view has no way from Issue sheet to Draft plan."])  # fmt: skip
    assert v.fit(v.path(["q"], {}, set()), DONE, LABELS) == (False, [v.NOTHING_MATCHED])


def test_the_steps_around_hidden_work() -> None:
    moves = [("x", "h", 9), ("y", "h", 2), ("h", "z", 11)]
    assert v.neighbours("h", moves, {"x": "a", "y": "b", "z": "c"}) == ("a", "c")
    assert v.neighbours("h", moves, {}) == (None, None)
