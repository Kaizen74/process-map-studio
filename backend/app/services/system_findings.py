"""System-record findings for Analysis A (PRD §3.13.6; criterion 88; R6). Pure and deterministic:
facts from Eric's confirmed alignment and the log's stored figures, no AI.

- `hidden_work`: an activity confirmed as having no step.
- `offline_work`: a step confirmed as having no system record that an interview describes.
- `dead_control_candidate`: a documented-only approval or decision with no system record (system
  evidence for Claude's finding of the same step, or a new finding).
- `sequence_drift`: a step the system trace contradicts (R5b).
- `estimate_gap`: a stated time more than 50% away from the measured median work.
- `measured_rework`: the step's activities repeat in more than 10% of cases.
Every finding rests on at least MINIMUM_CASES cases; figures are per step or activity, never per
person (constraint 24).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.enums import ElementKind
from app.domain.gap import GapEvidence, NewGapFinding
from app.services.grounding import words_to_digits

MINIMUM_CASES = 5
ESTIMATE_GAP = 0.5  # §3.13.6: flagged when the stated and measured times differ by more than this
REWORK = 0.10  # §3.13.6: measured rework above this share of cases
CONTROLS = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
DOCUMENTED_ONLY = "documented_only"
MINUTES = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)\s*(?:-\s*)?(?:minutes?|mins?)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FindingStep:
    key: str
    element_id: str
    label: str
    kind: str
    source_state: str
    times: Mapping[str, str] = field(default_factory=dict)  # account ("SME", "SOP") → its words


@dataclass(frozen=True, slots=True)
class LogFacts:
    """One imported log: Eric's confirmed decisions and the stored figures."""

    log_id: str
    name: str
    window: str  # "2026-03-02 to 2026-04-26", or ""
    cases: int  # all cases in the log
    matched: Mapping[str, str]  # activity → step key (confirmed)
    hidden: Sequence[str]  # activities confirmed as hidden work
    no_record: Sequence[str]  # step keys confirmed as having no system record
    activity_cases: Mapping[str, int]
    work_median: Mapping[str, float | None]  # activity → median work (end - start), if timed
    transitions: Sequence[tuple[str, str, int]]  # (from activity, to activity, cases)
    step_figures: Mapping[str, Mapping[str, int]]  # step key → cases, events, rework_cases
    contradictions: Mapping[str, str] = field(default_factory=dict)  # step key → the note


@dataclass
class SystemFindings:
    findings: list[NewGapFinding] = field(default_factory=list)
    # Extra evidence and a note for Claude's dead-control finding of a step (by step key).
    dead_control_support: dict[str, tuple[GapEvidence, str]] = field(default_factory=dict)


def stated_minutes(text: str) -> float | None:
    """The one minutes figure a time text states ("Within 10 minutes", "up to fifteen
    minutes"), or None when it states none or several (an unclear text is never compared)."""
    found = [float(m.group(1)) for m in MINUTES.finditer(words_to_digits(text))]
    return found[0] if len(found) == 1 else None


def _evidence(log: LogFacts, stance: str) -> GapEvidence:
    return GapEvidence(side="system", source_id=log.log_id, source_kind="system_log",
                       source_name=log.name, stance=stance, anchor=log.window)  # fmt: skip


def _share(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "0%"


def _finding(kind: str, title: str, text: str, step: FindingStep | None, severity: str,
             evidence: GapEvidence) -> NewGapFinding:  # fmt: skip
    return NewGapFinding(
        section="fact", finding_type=kind, title=title, text=text,
        element_ids=[step.element_id] if step else [], evidence=[evidence], provenance="O",
        severity=severity, verification_status="verified", verifier_verdict="not_run",
    )  # fmt: skip


def _hidden(log: LogFacts, by_key: Mapping[str, FindingStep], out: SystemFindings) -> None:
    for activity in log.hidden:
        cases = log.activity_cases.get(activity, 0)
        if cases < MINIMUM_CASES:
            continue
        before: dict[str, int] = {}
        for a, b, n in log.transitions:
            if b == activity and a in log.matched:
                before[log.matched[a]] = before.get(log.matched[a], 0) + n
        key = max(sorted(before), key=lambda k: before[k]) if before else None
        step = by_key.get(key) if key else None
        where = f", mostly right after {step.label}" if step else ""
        severity = "high" if step and step.kind in CONTROLS else "medium"
        out.findings.append(_finding(
            "hidden_work", f"System records work the map doesn't show: {activity}",
            f"The {log.name} log records “{activity}” in {cases} of {log.cases} cases "
            f"({_share(cases, log.cases)}){where}; no step on the map matches it.",
            step, severity, _evidence(log, "supports"),
        ))  # fmt: skip


def _unrecorded(log: LogFacts, by_key: Mapping[str, FindingStep], ai_dead: set[str],
                out: SystemFindings) -> None:  # fmt: skip
    if log.cases < MINIMUM_CASES:
        return
    for key in log.no_record:
        step = by_key.get(key)
        if step is None:
            continue
        silent = _evidence(log, "silent")
        if step.source_state == DOCUMENTED_ONLY and step.kind in CONTROLS:
            note = (f"System records: the {log.name} log has no record of {step.label} in "
                    f"{log.cases} cases.")  # fmt: skip
            if key in ai_dead:
                out.dead_control_support[key] = (silent, note)
            else:
                out.findings.append(_finding(
                    "dead_control_candidate", f"Documented control with no trace: {step.label}",
                    f"The documents describe {step.label}, no interview mentions it and the "
                    f"{log.name} log has no record of it in {log.cases} cases.",
                    step, "high", silent,
                ))  # fmt: skip
        elif step.source_state != DOCUMENTED_ONLY:
            out.findings.append(_finding(
                "offline_work", f"Work done outside the system: {step.label}",
                f"Interviews describe {step.label}, but the {log.name} log has no record of it "
                f"in {log.cases} cases: it is done offline or not recorded.",
                step, "medium" if step.kind in CONTROLS else "low", silent,
            ))  # fmt: skip


def _drift(log: LogFacts, by_key: Mapping[str, FindingStep], out: SystemFindings) -> None:
    for key, note in log.contradictions.items():
        step = by_key.get(key)
        if step is None:
            continue
        out.findings.append(_finding(
            "sequence_drift", f"The system records a different order: {step.label}",
            f"{note} The map puts it after.", step,
            "high" if step.kind in CONTROLS else "low", _evidence(log, "contradicts"),
        ))  # fmt: skip


def _main_activity(log: LogFacts, key: str) -> str | None:
    names = [a for a, k in log.matched.items() if k == key]
    return max(sorted(names), key=lambda a: log.activity_cases.get(a, 0)) if names else None


def _estimates(log: LogFacts, by_key: Mapping[str, FindingStep], out: SystemFindings) -> None:
    for key in sorted(set(log.matched.values())):
        step, activity = by_key.get(key), _main_activity(log, key)
        if step is None or activity is None:
            continue
        measured = log.work_median.get(activity)
        if measured is None or log.activity_cases.get(activity, 0) < MINIMUM_CASES:
            continue
        for account, text in step.times.items():
            stated = stated_minutes(text)
            if not stated or abs(measured - stated) / stated <= ESTIMATE_GAP:
                continue
            out.findings.append(_finding(
                "estimate_gap", f"Time differs from the stated time: {step.label}",
                f"{account} time for {step.label}: “{text}” ({stated:g} min). The {log.name} log "
                f"measures a median of {measured:g} min for “{activity}” "
                f"({_share(round(abs(measured - stated)), round(stated))} different).",
                step, "medium" if step.kind in CONTROLS else "low", _evidence(log, "supports"),
            ))  # fmt: skip


def _rework(log: LogFacts, by_key: Mapping[str, FindingStep], out: SystemFindings) -> None:
    for key, figures in sorted(log.step_figures.items()):
        step, cases, repeated = (
            by_key.get(key),
            figures.get("cases", 0),
            figures.get("rework_cases", 0),
        )
        if step is None or cases < MINIMUM_CASES or repeated / cases <= REWORK:
            continue
        names = ", ".join(sorted(a for a, k in log.matched.items() if k == key))
        out.findings.append(_finding(
            "measured_rework", f"Measured rework: {step.label}",
            f"The {log.name} log records {step.label} more than once in {repeated} of {cases} "
            f"cases ({_share(repeated, cases)}; activities: {names}).",
            step, "medium", _evidence(log, "supports"),
        ))  # fmt: skip


def findings(steps: Sequence[FindingStep], logs: Sequence[LogFacts],
             ai_dead: set[str]) -> SystemFindings:  # fmt: skip
    """Every system-record finding of the version's steps; `ai_dead` are the step keys Claude's
    findings already name as dead-control candidates."""
    by_key = {s.key: s for s in steps}
    out = SystemFindings()
    for log in logs:
        _hidden(log, by_key, out)
        _unrecorded(log, by_key, ai_dead, out)
        _drift(log, by_key, out)
        _estimates(log, by_key, out)
        _rework(log, by_key, out)
    return out
