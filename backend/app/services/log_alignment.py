"""Log activities → map steps (PRD §3.13.4; R5a): the deterministic first pass and the checks on
Claude's suggestions. Pure: names in, proposals out; nothing here is ever applied, Eric confirms.

- `propose`: for each activity, the step whose label (and SME terms) share the most words with
  it, with weight for the same role; or none (a hidden-work candidate).
- `check_suggestions`: Claude's suggestions kept only when they name an activity that was sent
  and a step that exists (constraint 2: no new names).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

STOP_WORDS = frozenset({"a", "an", "and", "at", "by", "for", "in", "is", "of", "ok", "on", "or",
                        "the", "to", "with"})  # fmt: skip
ENDINGS = ("ing", "ed", "es", "s", "e")
ROLE_WEIGHT = 0.25  # added when the activity's usual role is the step's lane role
MATCH = 0.5  # a proposal must score more than this: one shared word of two needs the same role


@dataclass(frozen=True, slots=True)
class ActivityInfo:
    name: str
    events: int = 0
    cases: int = 0
    role: str | None = None  # the role that records it most often


@dataclass(frozen=True, slots=True)
class StepInfo:
    key: str  # the step's stable key
    label: str
    kind: str = "activity"
    lane_role: str | None = None
    terms: tuple[str, ...] = field(default_factory=tuple)  # SME terms linked to the step


@dataclass(frozen=True, slots=True)
class Match:
    activity: str
    key: str
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class Suggestion:
    activity: str
    key: str
    reason: str


def _stem(word: str) -> str:
    for ending in ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def words(text: str) -> set[str]:
    """The comparable words of a name: lower case, simple endings removed, small words ignored."""
    found = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(w) for w in found if w not in STOP_WORDS}


def _score(activity: ActivityInfo, step: StepInfo) -> tuple[float, list[str], bool]:
    """The score, the activity's own words that match (as written) and whether the role does."""
    mine = words(activity.name)
    theirs = words(step.label).union(*(words(t) for t in step.terms))
    shared = mine & theirs
    if not shared:
        return 0.0, [], False
    same_role = bool(activity.role) and activity.role == step.lane_role
    base = len(shared) / min(len(mine), len(words(step.label)) or len(mine))
    written = [w for w in re.findall(r"[a-z0-9]+", activity.name.lower()) if _stem(w) in shared]
    as_written = list(dict.fromkeys(written))
    return min(base, 1.0) + (ROLE_WEIGHT if same_role else 0.0), as_written, same_role


def propose(activities: Sequence[ActivityInfo], steps: Sequence[StepInfo]) -> dict[str, Match]:
    """Each activity's best step when the match is strong enough (ties: same role first, then
    the step's order on the map). Activities with no match are left out."""
    out: dict[str, Match] = {}
    for activity in activities:
        best: tuple[float, bool, int] | None = None
        chosen: Match | None = None
        for order, step in enumerate(steps):
            score, shared, same_role = _score(activity, step)
            if score <= MATCH:
                continue
            rank = (score, same_role, -order)
            if best is None or rank > best:
                best = rank
                reason = f"Same words: {', '.join(shared)}."
                if same_role:
                    reason += f" Same role: {activity.role}."
                chosen = Match(activity.name, step.key, round(score, 2), reason)
        if chosen is not None:
            out[activity.name] = chosen
    return out


def check_suggestions(
    suggestions: Iterable[Suggestion], activities: Iterable[str], keys: Iterable[str]
) -> tuple[list[Suggestion], int]:
    """Claude's suggestions that name an activity that was sent and a step that exists, with a
    reason; at most one per activity (the first). The rest are counted, never shown."""
    allowed, existing = set(activities), set(keys)
    kept: list[Suggestion] = []
    seen: set[str] = set()
    left_out = 0
    for s in suggestions:
        reason = s.reason.strip()
        if s.activity not in allowed or s.key not in existing or not reason or s.activity in seen:
            left_out += 1
            continue
        seen.add(s.activity)
        kept.append(Suggestion(s.activity, s.key, reason))
    return kept, left_out
