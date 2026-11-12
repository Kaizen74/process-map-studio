"""The Reality snapshot's inputs and shared mechanics (PRD §3.18; P13b, P13c): what
`actions/reality` gathers, the figure register that keeps one value per figure ID (RQ9), and a
step's minutes. Pure: no database, no AI."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.compass import GradeView
from app.domain.reality import Figure
from app.services import discrepancies as rules
from app.services.discrepancies import Facts, StepFacts

PROCESS = "process"


# --- inputs (gathered by `actions/reality`) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PhaseIn:
    id: str
    name: str
    order: int


@dataclass(frozen=True, slots=True)
class RouteIn:
    """One log variant read through Eric's matches: its step keys ("" for an unmatched
    activity) and hidden-work activities, and whether it fits the As documented view."""

    rank: int
    cases: int
    share: float
    fits_documented: bool
    keys: tuple[str, ...]  # one per activity of the variant, in order ("" where unmatched)
    hidden: tuple[str, ...]
    activities: tuple[str, ...] = ()  # the log's activity names, in order
    positions: tuple[str, ...] = ()  # the step key at each activity ("" where none)
    # Per case of this variant: minutes from the case's start to each activity's start, then to
    # the case's finish (P13c Typical case; a composite of these cases, never one of them).
    timings: tuple[tuple[float, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class IntentIn:
    intent_id: str
    kind: str
    text: str
    scope: str  # step · phase · process
    step_keys: tuple[str, ...]
    phase_id: str | None
    metric: str | None
    comparator: str | None
    target: float | None
    unit: str | None
    result: str  # met · not_met · unknown


@dataclass(frozen=True, slots=True)
class ItemIn:
    item_id: str
    code: str
    title: str
    verdict_decided: str | None
    verdict_note: str
    grade: GradeView | None = None  # the shared grade (DECISIONS 96)


@dataclass(frozen=True, slots=True)
class Inputs:
    version_id: str
    process_name: str
    draft: bool
    data_label: str
    facts: Facts
    phases: tuple[PhaseIn, ...]
    step_phase: Mapping[str, str]  # step key → phase id ("" for none)
    routes: tuple[RouteIn, ...]
    routes_other: int  # variants too rare to show (under 5 cases)
    intents: tuple[IntentIn, ...]  # confirmed statements, in the order they were added
    items: Mapping[str, ItemIn]  # by location key
    documents: int  # SOPs and manuals
    interviews: int  # ready interview transcripts
    official_sources: Mapping[str, int]  # step key → interviews whose official account times it
    activity_after: Mapping[str, str]  # hidden-work activity → the step key it follows
    volume: float | None  # the process's cases a month (measured)
    cycle_min: float | None  # median case cycle time (measured)
    system_name: str = ""  # the first imported log's system of record
    # E1: the scope card says the process starts or ends outside the organisation (ticked by Eric).
    starts_outside: bool = False
    ends_outside: bool = False


def inputs_hash(inputs: Inputs) -> str:
    text = json.dumps(dataclasses.asdict(inputs), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- figures ------------------------------------------------------------------------------------


class Figures:
    """Every figure of the snapshot by its ID: one value and one text everywhere (RQ9)."""

    def __init__(self) -> None:
        self.by_id: dict[str, Figure] = {}

    def add(self, fid: str, value: float | None, unit: str, text: str, label: str,
            percent_type: str | None = None) -> Figure:  # fmt: skip
        figure = Figure(id=fid, value=value, unit=unit, text=text, label=label,
                        percent_type=percent_type)  # fmt: skip
        known = self.by_id.get(fid)
        assert known is None or known == figure, f"two values for {fid}"
        self.by_id[fid] = figure
        return figure


def blend(labels: Sequence[str]) -> str:
    found = set(labels)
    return found.pop() if len(found) == 1 else rules.MEASURED if not found else "mixed"


Part = tuple[float, str] | None  # minutes and their label


def step_parts(s: StepFacts) -> tuple[Part, Part]:
    """A step's work and wait a case, each with its label: measured where measured. When the
    step's accounts state a wait, its measured activity time is that wait (see the engine)."""
    measured = s.time if s.time and s.time.cases >= rules.MINIMUM_CASES else None
    before = s.wait_before if s.wait_before and s.wait_before.cases >= rules.MINIMUM_CASES else None
    if s.stated_wait is not None and measured is not None:
        work = (s.done_min, rules.STATED) if s.done_min is not None else None
        wait: tuple[float, str] | None = (measured.median, rules.MEASURED)
    else:
        work = (measured.median, rules.MEASURED) if measured else (
            (s.done_min, rules.STATED) if s.done_min is not None else None)  # fmt: skip
        wait = (before.median, rules.MEASURED) if before else (
            (s.stated_wait, rules.STATED) if s.stated_wait is not None else None)  # fmt: skip
    return work, wait


def step_minutes(s: StepFacts) -> tuple[float | None, str]:
    """A step's minutes a case (work and wait) and their label."""
    parts = [p for p in step_parts(s) if p is not None]
    if not parts:
        return None, ""
    return round(sum(v for v, _ in parts), 1), blend([lb for _, lb in parts])
