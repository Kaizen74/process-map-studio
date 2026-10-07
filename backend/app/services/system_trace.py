"""System trace on the map (PRD §3.13.4, §3.12.7; criterion 87; R5b). Pure: what Eric's confirmed
alignment of a log does to a map's lines, source states and divergences, and the trace evidence of
each step. Figures in, overlay out; the caller decides when it applies (a draft every read, a
published version once, frozen).

- A line A → B, both steps matched, is `system_trace` when the log records A's activity directly
  followed by B's in at least MINIMUM_CASES cases, and more often than the reverse.
- When the reverse is recorded in at least MINIMUM_CASES cases and more often, the order is
  contradicted: B becomes `trace_contradicted` (if it had support) with divergence `sequence`.
- A matched step recorded in at least MINIMUM_CASES cases corroborates a one-sided account:
  `practiced_only` and `documented_only` become `corroborated`.
A step with no system record is the system being silent: it never contradicts (constraint 4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import DivergenceType, SequenceBasis, SourceState

MINIMUM_CASES = 5  # §3.13.5: nothing rests on fewer cases
SUPPORTS, CONTRADICTS = "supports", "contradicts"
ONE_SIDED = {SourceState.PRACTICED_ONLY.value, SourceState.DOCUMENTED_ONLY.value}
SUPPORTED = {SourceState.CORROBORATED.value, SourceState.CONTESTED.value, *ONE_SIDED}
SEQUENCE = DivergenceType.SEQUENCE.value


@dataclass(frozen=True, slots=True)
class TraceStep:
    key: str
    label: str
    source_state: str
    divergence_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TraceEdge:
    id: str
    from_key: str
    to_key: str


@dataclass(frozen=True, slots=True)
class TraceLog:
    """One imported log with Eric's confirmed matches and its stored metrics."""

    log_id: str
    matched: Mapping[str, str]  # activity → step key (confirmed rows only)
    activity_cases: Mapping[str, int]  # activity → cases
    transitions: Sequence[tuple[str, str, int]]  # (from activity, to activity, cases)


@dataclass
class Overlay:
    edge_basis: dict[str, str] = field(default_factory=dict)  # edge ID → system_trace
    states: dict[str, str] = field(default_factory=dict)  # step key → new source state
    divergences: dict[str, list[str]] = field(default_factory=dict)  # step key → new list
    stances: dict[tuple[str, str], str] = field(default_factory=dict)  # (log, key) → stance
    notes: dict[tuple[str, str], str] = field(default_factory=dict)  # (log, key) → words


def recorded_steps(log: TraceLog) -> dict[str, int]:
    """Each matched step and the most cases any one of its activities is recorded in (a lower
    bound for the step's own cases, which is enough to apply the 5-case minimum)."""
    out: dict[str, int] = {}
    for activity, key in log.matched.items():
        out[key] = max(out.get(key, 0), log.activity_cases.get(activity, 0))
    return out


def step_moves(log: TraceLog) -> dict[tuple[str, str], int]:
    """Cases where one matched step's activity is directly followed by another step's, summed
    over the activity pairs; moves within one step (rework) are left out."""
    out: dict[tuple[str, str], int] = {}
    for a, b, cases in log.transitions:
        ka, kb = log.matched.get(a), log.matched.get(b)
        if ka and kb and ka != kb:
            out[(ka, kb)] = out.get((ka, kb), 0) + cases
    return out


def overlay(steps: Sequence[TraceStep], edges: Sequence[TraceEdge],
            logs: Sequence[TraceLog]) -> Overlay:  # fmt: skip
    """What the confirmed alignment of every log does to this map."""
    by_key = {s.key: s for s in steps}
    out = Overlay()
    contradicted: set[str] = set()
    supported: set[str] = set()
    for log in logs:
        recorded = {k: n for k, n in recorded_steps(log).items()
                    if k in by_key and n >= MINIMUM_CASES}  # fmt: skip
        moves = step_moves(log)
        for key in recorded:
            supported.add(key)
            out.stances[(log.log_id, key)] = SUPPORTS
        for edge in edges:
            if edge.from_key not in recorded or edge.to_key not in recorded:
                continue
            forward = moves.get((edge.from_key, edge.to_key), 0)
            backward = moves.get((edge.to_key, edge.from_key), 0)
            if forward >= MINIMUM_CASES and forward > backward:
                out.edge_basis[edge.id] = SequenceBasis.SYSTEM_TRACE.value
            elif backward >= MINIMUM_CASES and backward > forward:
                contradicted.add(edge.to_key)
                out.stances[(log.log_id, edge.to_key)] = CONTRADICTS
                first, then = by_key[edge.to_key].label, by_key[edge.from_key].label
                out.notes[(log.log_id, edge.to_key)] = (
                    f"The system records {first} before {then} in {backward} cases."
                )
    for key in supported | contradicted:
        step = by_key[key]
        if key in contradicted:
            if step.source_state in SUPPORTED:
                out.states[key] = SourceState.TRACE_CONTRADICTED.value
            if SEQUENCE not in step.divergence_types:
                out.divergences[key] = [*step.divergence_types, SEQUENCE]
        elif step.source_state in ONE_SIDED:
            out.states[key] = SourceState.CORROBORATED.value
    return out


def trace_item(step: TraceStep, element_id: str, log: Mapping[str, Any],
               figures: Mapping[str, Any], activities: list[dict[str, Any]],
               stance: str, note: str) -> dict[str, Any]:  # fmt: skip
    """One step's system-trace evidence from one log (API_CONTRACT → system-traces)."""
    weeks = max(int(log.get("weeks") or 1), 1)
    cases = int(figures.get("cases", 0))
    rework = int(figures.get("rework_cases", 0))
    return {
        "element_id": element_id, "label": step.label, "stance": stance,
        "log_id": log["id"], "log_name": log["name"], "system": log.get("system", ""),
        "window_start": log.get("window_start"), "window_end": log.get("window_end"),
        "cases": cases, "events": int(figures.get("events", 0)),
        "cases_per_week": round(cases / weeks, 1), "rework_cases": rework,
        "rework_share": round(rework / cases, 3) if cases else 0.0,
        "activities": activities, "note": note,
    }  # fmt: skip
