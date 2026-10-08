"""The system's variants read through Eric's confirmed matches and compared with the map's views
(API_CONTRACT.md → system-variants; PRD §5.6 Variants tab, §3.13.4; criterion 89; R8). Pure and
deterministic: figures come from the stored metrics, nothing is worked out per person.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

MINIMUM_CASES = 5  # §3.13.5: nothing rests on fewer cases
MATCHED, HIDDEN, NOT_MATCHED = "matched", "hidden_work", "not_matched"
VIEW_NAMES = {"done": "As done", "documented": "As documented"}
NOTHING_MATCHED = "No activity of this variant is matched to a step yet."


@dataclass(frozen=True, slots=True)
class PathStep:
    activity: str
    key: str | None  # the matched step's stable key
    status: str  # matched · hidden_work · not_matched


@dataclass(frozen=True, slots=True)
class ViewMap:
    """One view of the version: its steps (stable key → label) and its lines between steps."""

    name: str  # done · documented
    labels: Mapping[str, str]
    lines: Sequence[tuple[str, str]]


def path(activities: Sequence[str], matched: Mapping[str, str], hidden: set[str]) -> list[PathStep]:
    """A variant's activities with what Eric decided for each."""
    out = []
    for activity in activities:
        if activity in matched:
            out.append(PathStep(activity, matched[activity], MATCHED))
        else:
            out.append(PathStep(activity, None, HIDDEN if activity in hidden else NOT_MATCHED))
    return out


def _reachable(lines: Sequence[tuple[str, str]], start: str) -> set[str]:
    nexts: dict[str, list[str]] = {}
    for a, b in lines:
        nexts.setdefault(a, []).append(b)
    seen: set[str] = set()
    todo = list(nexts.get(start, []))
    while todo:
        step = todo.pop()
        if step not in seen:
            seen.add(step)
            todo.extend(nexts.get(step, []))
    return seen


def fit(steps: Sequence[PathStep], view: ViewMap,
        labels: Mapping[str, str]) -> tuple[bool, list[str]]:  # fmt: skip
    """Whether the variant fits a view, and what doesn't, in words. `labels` names every step of
    the version (stable key → label), so a step outside the view can still be named."""
    name = VIEW_NAMES.get(view.name, view.name)
    notes: list[str] = []
    for s in steps:
        if s.status == HIDDEN:
            notes.append(f"{s.activity} is hidden work: no step on the map.")
        elif s.status == NOT_MATCHED:
            notes.append(f"{s.activity} isn't matched to a step yet.")
    keys: list[str] = []
    for s in steps:
        if s.key is not None and (not keys or keys[-1] != s.key):
            keys.append(s.key)  # a step repeated straight after itself counts once
    if not keys:
        return False, [NOTHING_MATCHED]
    missing = [k for k in dict.fromkeys(keys) if k not in view.labels]
    notes += [f"{labels.get(k, k)} isn't in the {name} view." for k in missing]
    for a, b in pairwise(keys):
        if a in view.labels and b in view.labels and b not in _reachable(view.lines, a):
            notes.append(f"The {name} view has no way from {labels[a]} to {labels[b]}.")
    notes = list(dict.fromkeys(notes))
    return not notes, notes


def neighbours(activity: str, transitions: Sequence[tuple[str, str, int]],
               matched: Mapping[str, str]) -> tuple[str | None, str | None]:  # fmt: skip
    """The matched steps an activity most often directly follows and precedes (stable keys)."""
    before: dict[str, int] = {}
    after: dict[str, int] = {}
    for a, b, n in transitions:
        if b == activity and a in matched:
            before[matched[a]] = before.get(matched[a], 0) + n
        if a == activity and b in matched:
            after[matched[b]] = after.get(matched[b], 0) + n

    def top(counts: dict[str, int]) -> str | None:
        return max(sorted(counts), key=lambda k: counts[k]) if counts else None

    return top(before), top(after)
