"""Intent evaluation (PRD §3.16 "Evaluation"; P13a). Deterministic, never AI.

A confirmed statement with a metric is compared with the done view, in this order of evidence:
measured (system records, at least 5 cases) → the lived accounts' stated value → the documented
value. The result is met, not met or unknown, with the share of cases meeting the target when
cases are measured, and the figure label (B.50). A statement without a metric is evaluated only
through confirmed discrepancies on the steps it covers (`evaluate_without_metric`). "Unknown" is
shown honestly, never as met.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import FigureLabel

MINIMUM_CASES = 5
MET, NOT_MET, UNKNOWN = "met", "not_met", "unknown"
# A control objective is not met where a step it covers shows one of these (§3.16).
CONTROL_FAILURES = frozenset({"D1", "D5", "D11"})


@dataclass(frozen=True, slots=True)
class Target:
    metric: str
    comparator: str  # at_most · at_least · equals
    value: float


@dataclass(frozen=True, slots=True)
class Values:
    """What the app knows of one quantity on the steps a statement covers."""

    measured: float | None = None
    measured_cases: int = 0
    within: int | None = None  # measured cases meeting the target (when worked out per case)
    stated: float | None = None  # the lived accounts' value
    documented: float | None = None


@dataclass(frozen=True, slots=True)
class Evaluation:
    result: str  # met · not_met · unknown
    actual: float | None = None
    label: str | None = None  # B.50: measured · stated · documented
    met_share: float | None = None  # share of measured cases meeting the target
    cases: int | None = None
    documented: float | None = None
    documented_meets: bool | None = None


def meets(target: Target, value: float) -> bool:
    if target.comparator == "at_most":
        return value <= target.value
    if target.comparator == "at_least":
        return value >= target.value
    return value == target.value


def evaluate(target: Target, values: Values) -> Evaluation:
    """A statement with a metric against the done view."""
    documented = values.documented
    doc_meets = meets(target, documented) if documented is not None else None
    if values.measured is not None and values.measured_cases >= MINIMUM_CASES:
        share = (values.within / values.measured_cases) if values.within is not None else None
        return Evaluation(
            MET if meets(target, values.measured) else NOT_MET, values.measured,
            FigureLabel.MEASURED.value, share, values.measured_cases, documented, doc_meets,
        )  # fmt: skip
    if values.stated is not None:
        return Evaluation(MET if meets(target, values.stated) else NOT_MET, values.stated,
                          FigureLabel.STATED.value, None, None, documented, doc_meets)  # fmt: skip
    if documented is not None:
        label = FigureLabel.DOCUMENTED.value
        return Evaluation(MET if doc_meets else NOT_MET, documented, label, None, None,
                          documented, doc_meets)  # fmt: skip
    return Evaluation(UNKNOWN)


def evaluate_without_metric(kind: str, failures: list[tuple[str, float | None, int | None]]
                            ) -> Evaluation:  # fmt: skip
    """A statement without a metric: a control objective is not met for the share of cases a
    D1, D5 or D11 on a step it covers shows (`failures`: type, share of cases, cases); anything
    else is unknown."""
    if kind != "control_objective":
        return Evaluation(UNKNOWN)
    found = [(share, cases) for t, share, cases in failures if t in CONTROL_FAILURES]
    if not found:
        return Evaluation(UNKNOWN)
    shares = [s for s, _ in found if s is not None]
    share = max(shares) if shares else None
    cases = max((c for _, c in found if c is not None), default=None)
    label = FigureLabel.MEASURED.value if share is not None else FigureLabel.STATED.value
    met_share = (1 - share) if share is not None else None
    return Evaluation(NOT_MET, None, label, met_share, cases)
