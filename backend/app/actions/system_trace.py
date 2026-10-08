"""System trace on the map (API_CONTRACT.md → System trace on the map; PRD §3.13.4; criterion 87;
R5b).

A draft shows Eric's confirmed alignment every time it is read (`applied`, called by
`versions.build_graph`); publishing freezes it into the version (`freeze`), so a published version
never changes when the alignment does. Unconfirmed proposals never touch a map.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.db import session_scope
from app.domain.enums import ElementKind, VersionState
from app.domain.graph import EdgeRecord, ElementRecord, Graph, GraphElement
from app.domain.models import VersionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.system_records import EventLogView, SystemTraceItem
from app.repositories import elements as map_repo
from app.repositories import event_logs as logs_repo
from app.repositories import versions as versions_repo
from app.services import system_findings as finding_rules
from app.services import system_trace as tracing
from app.services.system_findings import FindingStep, LogFacts, SystemFindings
from app.services.system_trace import Overlay, TraceEdge, TraceLog, TraceStep

Sessions = sessionmaker[Session]

VERSION_MISSING = "That version doesn't exist."
NOT_STEPS = {ElementKind.START.value, ElementKind.END.value}


def _moves(session: Session, log_id: str) -> list[tuple[str, str, int]]:
    """(from activity, to activity, cases) for every recorded transition of the log."""
    rows = logs_repo.metrics(session, log_id, "transition")
    return [(str(r.metrics["from_activity"]), str(r.metrics["to_activity"]),
             int(r.metrics["cases"])) for r in rows]  # fmt: skip


def _logs(session: Session, engagement_id: str) -> list[tuple[EventLogView, TraceLog]]:
    out = []
    for log, matched in logs_repo.confirmed_matches(session, engagement_id):
        activities = logs_repo.metrics(session, log.id, "activity")
        out.append((log, TraceLog(
            log_id=log.id, matched=matched,
            activity_cases={r.key: r.case_count for r in activities},
            transitions=_moves(session, log.id),
        )))  # fmt: skip
    return out


def _steps(elements: Sequence[ElementRecord]) -> list[TraceStep]:
    return [TraceStep(e.stable_key, e.label, e.source_state, tuple(e.divergence_types))
            for e in elements if e.kind not in NOT_STEPS]  # fmt: skip


def _edges(elements: Sequence[ElementRecord], edges: Sequence[EdgeRecord]) -> list[TraceEdge]:
    keys = {e.id: e.stable_key for e in elements}
    return [TraceEdge(x.id, keys[x.from_element_id], keys[x.to_element_id])
            for x in edges if x.from_element_id in keys and x.to_element_id in keys]  # fmt: skip


Traced = list[tuple[EventLogView, TraceLog]]


def _overlay(session: Session, version: VersionView, elements: Sequence[ElementRecord],
             edges: Sequence[EdgeRecord]) -> tuple[Overlay, Traced]:  # fmt: skip
    logs = _logs(session, version.engagement_id)
    return tracing.overlay(_steps(elements), _edges(elements, edges), [t for _, t in logs]), logs


def applied(session: Session, version: VersionView, elements: list[ElementRecord],
            edges: list[EdgeRecord]) -> tuple[list[ElementRecord], list[EdgeRecord]]:  # fmt: skip
    """A draft's elements and lines with the confirmed system trace; anything else unchanged."""
    if version.state != VersionState.DRAFT.value:
        return elements, edges
    overlay, logs = _overlay(session, version, elements, edges)
    if not logs:
        return elements, edges
    return _with(overlay, elements, edges)


def _with(overlay: Overlay, elements: list[ElementRecord],
          edges: list[EdgeRecord]) -> tuple[list[ElementRecord], list[EdgeRecord]]:  # fmt: skip
    changed = []
    for e in elements:
        update: dict[str, Any] = {}
        if e.stable_key in overlay.states:
            update["source_state"] = overlay.states[e.stable_key]
        if e.stable_key in overlay.divergences:
            update["divergence_types"] = overlay.divergences[e.stable_key]
        changed.append(e.model_copy(update=update) if update else e)
    lines = [x.model_copy(update={"sequence_basis": overlay.edge_basis[x.id]})
             if x.id in overlay.edge_basis else x for x in edges]  # fmt: skip
    return changed, lines


def _items(session: Session, version: VersionView, elements: Sequence[ElementRecord],
           edges: Sequence[EdgeRecord]) -> list[SystemTraceItem]:  # fmt: skip
    overlay, logs = _overlay(session, version, elements, edges)
    steps = [e for e in elements if e.kind not in NOT_STEPS]
    items: list[SystemTraceItem] = []
    for element in steps:
        for log, trace in logs:
            stance = overlay.stances.get((log.id, element.stable_key))
            if stance is None:
                continue
            names = {a for a, k in trace.matched.items() if k == element.stable_key}
            figures = logs_repo.step_figures(session, log.id, names)
            if figures["cases"] < tracing.MINIMUM_CASES:
                continue
            rows = [r for r in logs_repo.metrics(session, log.id, "activity")
                    if r.key in names and r.case_count >= tracing.MINIMUM_CASES]  # fmt: skip
            case = next(iter(logs_repo.metrics(session, log.id, "case")), None)
            weeks = case.metrics.get("weeks", 1) if case else 1
            activities = [{"activity": r.key, "cases": r.case_count,
                           "events": r.metrics["events"], "work": r.metrics["work"],
                           "wait_before": r.metrics["wait_before"], "basis": r.metrics["basis"]}
                          for r in rows]  # fmt: skip
            step = TraceStep(element.stable_key, element.label, element.source_state)
            info = log.model_dump() | {"weeks": weeks}
            note = overlay.notes.get((log.id, element.stable_key), "")
            items.append(SystemTraceItem.model_validate(tracing.trace_item(
                step, element.id, info, figures, activities, stance, note
            )))  # fmt: skip
    return items


def get_system_traces(sessions: Sessions, version_id: str) -> Result[list[SystemTraceItem]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        if version.state != VersionState.DRAFT.value:
            frozen = versions_repo.system_traces(session, version_id) or []
            return Ok([SystemTraceItem.model_validate(i) for i in frozen])
        elements = map_repo.elements(session, version_id)
        edges = map_repo.edges(session, version_id)
        return Ok(_items(session, version, elements, edges))


def freeze(session: Session, version_id: str) -> None:
    """At publishing: write the draft's system trace into the version for good."""
    version = versions_repo.get(session, version_id)
    if version is None or version.state != VersionState.DRAFT.value:
        return
    elements = map_repo.elements(session, version_id)
    edges = map_repo.edges(session, version_id)
    items = _items(session, version, elements, edges)
    overlay, logs = _overlay(session, version, elements, edges)
    if logs:
        changed, lines = _with(overlay, elements, edges)
        for before, after in zip(elements, changed, strict=True):
            if after is not before:
                map_repo.update_element(session, after.id, {
                    "source_state": after.source_state, "divergence_types": after.divergence_types,
                })  # fmt: skip
        for line in lines:
            if line.id in overlay.edge_basis:
                map_repo.set_edge_basis(session, line.id, overlay.edge_basis[line.id])
    versions_repo.set_system_traces(session, version_id, [i.model_dump() for i in items])


# --- System-record findings for Analysis A (R6) ------------------------------------------------


def _times(element: GraphElement) -> dict[str, str]:
    """The step's stated times in each account's own words."""
    variants = element.variants or {}
    done = variants.get("done", {}).get("time", "")
    documented = variants.get("documented", {}).get("time", "")
    if done or documented:
        return {k: v for k, v in (("SME", done), ("Documented", documented)) if v}
    return {"Stated": element.time.text} if element.time.text else {}


def _log_facts(session: Session, log: EventLogView, keys: dict[str, str],
               items: list[SystemTraceItem]) -> LogFacts | None:  # fmt: skip
    decided = [s for s in logs_repo.alignment(session, log.id) if s.confirmed]
    matched = {s.activity: s.step_key for s in decided
               if s.status == "confirmed" and s.activity and s.step_key}  # fmt: skip
    hidden = [s.activity for s in decided if s.status == "hidden_work" and s.activity]
    no_record = [s.step_key for s in decided
                 if s.status == "no_system_record" and s.step_key]  # fmt: skip
    if not (matched or hidden or no_record):
        return None
    activities = logs_repo.metrics(session, log.id, "activity")
    case = next(iter(logs_repo.metrics(session, log.id, "case")), None)
    work = {r.key: (r.metrics["work"] or {}).get("median_min") for r in activities}
    moves = _moves(session, log.id)
    figures = {key: logs_repo.step_figures(session, log.id, {a for a, k in matched.items()
                                                             if k == key})
               for key in set(matched.values())}  # fmt: skip
    window = (
        f"{log.window_start} to {log.window_end}" if log.window_start and log.window_end else ""
    )
    contradictions = {keys[i.element_id]: i.note for i in items if i.log_id == log.id
                      and i.stance == "contradicts" and i.element_id in keys}  # fmt: skip
    return LogFacts(
        log_id=log.id, name=log.name, window=window, cases=case.case_count if case else 0,
        matched=matched, hidden=hidden, no_record=no_record,
        activity_cases={r.key: r.case_count for r in activities}, work_median=work,
        transitions=moves, step_figures=figures, contradictions=contradictions,
    )  # fmt: skip


def system_findings(session: Session, version: VersionView, graph: Graph,
                    ai_dead: set[str]) -> SystemFindings:  # fmt: skip
    """The version's system-record findings from Eric's confirmed alignment (§3.13.6)."""
    elements = map_repo.elements(session, version.id)
    keys = {e.id: e.stable_key for e in elements}
    steps = [FindingStep(keys[g.id], g.id, g.label, g.kind, g.source_state, _times(g))
             for g in graph.elements if g.kind not in NOT_STEPS and g.id in keys]  # fmt: skip
    if version.state == VersionState.DRAFT.value:
        items = _items(session, version, elements, map_repo.edges(session, version.id))
    else:
        frozen = versions_repo.system_traces(session, version.id) or []
        items = [SystemTraceItem.model_validate(i) for i in frozen]
    logs = [facts for log in logs_repo.list_for(session, version.engagement_id)
            if log.status == "imported"
            and (facts := _log_facts(session, log, keys, items)) is not None]  # fmt: skip
    return finding_rules.findings(steps, logs, ai_dead)
