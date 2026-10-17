"""The value calculator (PRD §3.14; criterion 90; R9b). Pure and deterministic: every figure comes
with its evidence label, scenarios are potential, and money is per step and phase, never per
person.

Inputs per step, in the PRD's order of preference: measured from system records → the SME's
estimate (the step's verified time) → Eric's override (with a note).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.enums import StepDisposition, ValueEvidence

MEASURED = ValueEvidence.MEASURED.value
ESTIMATED = ValueEvidence.ESTIMATED.value
MIXED = ValueEvidence.MIXED.value
ASSUMED = ValueEvidence.ASSUMED.value
POTENTIAL = "Potential, not committed"
DEFAULT_REDUCTION: Mapping[str, float] = {
    StepDisposition.DELETE.value: 100.0,
    StepDisposition.AUTOMATE_RULES.value: 80.0,
    StepDisposition.AI_ASSISTED.value: 50.0,
    StepDisposition.HUMAN_APPROVES.value: 30.0,
    StepDisposition.KEEP_HUMAN.value: 0.0,
}


@dataclass(frozen=True, slots=True)
class Figure:
    value: float
    label: str  # measured · estimated · assumed
    source: str  # in words: where it comes from


@dataclass(frozen=True, slots=True)
class StepInputs:
    """What one step's value is worked out from."""

    element_id: str
    measured_time: Figure | None = None
    estimated_time: Figure | None = None
    override_time: Figure | None = None
    measured_volume: Figure | None = None
    estimated_volume: Figure | None = None
    override_volume: Figure | None = None
    hourly_cost: float | None = None  # the lane role's loaded hourly cost
    role_name: str = ""
    disposition: str = "keep_human"  # Eric's choice, else the suggestion
    chosen: bool = False


@dataclass(frozen=True, slots=True)
class StepValue:
    element_id: str
    time: Figure | None
    volume: Figure | None
    hours: float | None
    cost: float | None
    label: str | None
    missing: list[str]
    disposition: str
    chosen: bool
    reduction_pct: float
    hours_released: float | None
    cost_released: float | None


def first(*figures: Figure | None) -> Figure | None:
    """The first figure that exists, in the PRD's order of preference."""
    return next((f for f in figures if f is not None), None)


def combined(labels: Sequence[str]) -> str | None:
    """One label for figures worked out together: the same label, else mixed."""
    if not labels:
        return None
    return labels[0] if len(set(labels)) == 1 else MIXED


def step_value(step: StepInputs, reductions: Mapping[str, float]) -> StepValue:
    time = first(step.measured_time, step.estimated_time, step.override_time)
    volume = first(step.measured_volume, step.estimated_volume, step.override_volume)
    missing = []
    if time is None:
        missing.append("No time per case: none measured, none stated, no override.")
    if volume is None:
        missing.append("No volume per month: none measured, no override.")
    hours = round(time.value * volume.value / 60, 1) if time and volume else None
    cost = None
    if hours is not None and step.hourly_cost is None:
        missing.append(f"No hourly cost for {step.role_name or 'the lane role'}.")
    elif hours is not None and step.hourly_cost is not None:
        cost = round(hours * step.hourly_cost, 2)
    label = combined([f.label for f in (time, volume) if f]) if hours is not None else None
    pct = float(reductions.get(step.disposition, DEFAULT_REDUCTION.get(step.disposition, 0.0)))
    return StepValue(
        element_id=step.element_id, time=time, volume=volume, hours=hours, cost=cost,
        label=label, missing=missing, disposition=step.disposition, chosen=step.chosen,
        reduction_pct=pct,
        hours_released=round(hours * pct / 100, 1) if hours is not None else None,
        cost_released=round(cost * pct / 100, 2) if cost is not None else None,
    )  # fmt: skip


@dataclass
class Total:
    hours: float = 0.0
    cost: float = 0.0
    labels: list[str] = field(default_factory=list)
    counted: int = 0
    missing: int = 0
    costed: int = 0

    def add(self, v: StepValue) -> None:
        if v.hours is None:
            self.missing += 1
            return
        self.counted += 1
        self.hours = round(self.hours + v.hours, 1)
        if v.label:
            self.labels.append(v.label)
        if v.cost is not None:
            self.costed += 1
            self.cost = round(self.cost + v.cost, 2)

    @property
    def label(self) -> str | None:
        return combined(sorted(set(self.labels))) if self.labels else None


def totals(values: Sequence[StepValue], groups: Mapping[str, str | None]) -> dict[str, Total]:
    """Sums per group (a phase ID → its steps); steps without figures are counted as missing."""
    out: dict[str, Total] = {}
    for v in values:
        key = groups.get(v.element_id) or ""
        out.setdefault(key, Total()).add(v)
    return out


def scenarios(values: Sequence[StepValue]) -> dict[str, dict[str, float | int]]:
    """Per disposition: steps, hours and the capacity and cost it could release (potential)."""
    out: dict[str, dict[str, float | int]] = {}
    for d in DEFAULT_REDUCTION:
        rows = [v for v in values if v.disposition == d]
        out[d] = {
            "steps": len(rows),
            "hours": round(sum(v.hours or 0 for v in rows), 1),
            "hours_released": round(sum(v.hours_released or 0 for v in rows), 1),
            "cost_released": round(sum(v.cost_released or 0 for v in rows), 2),
        }
    return out
