"""The discrepancy engine's facts (PRD §3.17.1; P13a): read from what the app already holds and
handed to the pure rules (`services/discrepancies`, `services/intent`). No AI call is made here
or anywhere the engine runs (constraint 26).

Facts only: the version's two views, verified claims behind the steps, Eric's confirmed system
alignment and the log's stored figures (groups of at least 5 cases), confirmed intent statements
and confirmed design gaps. Rejected steps, rejected claims and unconfirmed proposals are never
inputs.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import system_trace
from app.actions import versions as versions_action
from app.db import session_scope
from app.domain.enums import ReviewStatus, SourceKind
from app.domain.graph import Graph, GraphElement
from app.domain.models import ClaimRecord, VersionView
from app.domain.reality import (
    DeltaView,
    Detection,
    DiscrepancyFound,
    IntentEvaluationView,
    IntentRecord,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import ExceptionEdgeInput, ExceptionStepInput
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import event_logs as logs_repo
from app.repositories import intent as intent_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import discrepancies as rules
from app.services import exceptions, grounding
from app.services import intent as evaluation
from app.services.system_findings import LogFacts, stated_minutes

Sessions = sessionmaker[Session]

STEP_KINDS = {"activity", "decision", "approval"}
DOCUMENT_KINDS = {SourceKind.SOP.value, SourceKind.MANUAL.value}
INTERVIEW = SourceKind.INTERVIEW_TRANSCRIPT.value
ARTEFACT = SourceKind.EXECUTED_ARTEFACT.value
TOOL_SOURCES = {SourceKind.WORKING_SPREADSHEET.value: "spreadsheet",
                SourceKind.EMAIL_THREAD.value: "email"}  # fmt: skip
TOOL_CLAIMS = {"activity", "exception", "handoff", "approval", "decision"}
LANDSCAPE = re.compile(r"L[1-7]")
Offsets = tuple[float | None, float | None]  # a step's (lived, documented) time offsets


def _minutes(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60


def _offset(text: str) -> float | None:
    """The one time offset a text states ("by T-90" → 90), or None."""
    found = [n for n in grounding.numbers_in(text) if n.startswith("T-")]
    return float(found[0][2:]) if len(found) == 1 else None


def _practice_interviews(session: Session, engagement_id: str) -> set[str]:
    """Ready interview transcripts that aren't wholly Landscape interviews (Appendix F)."""
    out = set()
    for s in sources_repo.list_for_engagement(session, engagement_id):
        if s.kind != INTERVIEW or s.text_status != "ready":
            continue
        asked = sources_repo.question_ids(session, s.id)
        if not asked or not all(LANDSCAPE.fullmatch(q) for q in asked):
            out.add(s.id)
    return out


def _claims(session: Session, version_id: str) -> dict[str, list[ClaimRecord]]:
    links = map_repo.element_claims(session, version_id)
    found = claims_repo.by_ids(session, [c for ids in links.values() for c in ids])
    return {element_id: [found[c] for c in ids
                         if c in found and found[c].verification_status == "verified"]
            for element_id, ids in links.items()}  # fmt: skip


def _words(c: ClaimRecord) -> str:
    return " ".join(str(c.payload.get(k) or "") for k in ("text", "duration_text", "threshold"))


def _tools(claims: list[ClaimRecord], kinds: Mapping[str, str]) -> tuple[str, ...]:
    found: set[str] = set()
    for c in claims:
        kind = kinds.get(c.source_id, "")
        if kind in TOOL_SOURCES:
            found.add(TOOL_SOURCES[kind])
        if kind == INTERVIEW and c.account_type == "lived" and c.claim_type in TOOL_CLAIMS:
            text = f"{c.payload.get('text') or ''} {c.quote}".casefold()
            for word in rules.NOT_TOOLS:
                text = text.replace(word, " ")
            found |= {w for w in rules.TOOL_WORDS
                      if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text)}  # fmt: skip
    return tuple(sorted(found))


def _usual_route(graph: Graph, conditions: dict[str, str]) -> set[str]:
    steps = [ExceptionStepInput(element_id=e.id, label=e.label, kind=e.kind,
                                condition=conditions.get(e.id, ""))
             for e in graph.elements]  # fmt: skip
    lines = [ExceptionEdgeInput(from_id=e.from_, to_id=e.to, kind=e.kind, label=e.label)
             for e in graph.edges]  # fmt: skip
    minutes = {e.id: float((e.time.work_min or 0) + (e.time.wait_min or 0))
               for e in graph.elements}  # fmt: skip
    return set(exceptions.usual_path(steps, lines, minutes))


def _measure(row: Mapping[str, object] | None, cases: int) -> rules.Measure | None:
    if not isinstance(row, Mapping) or row.get("median_min") is None:
        return None
    p90 = row.get("p90_min")
    n = row.get("n")
    return rules.Measure(float(str(row["median_min"])), float(str(p90)) if p90 is not None
                         else None, int(str(n)) if n is not None else cases)  # fmt: skip


def _system(key: str, logs: list[LogFacts],
            rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:  # fmt: skip
    """What the first log covering the step says of it (empty: no imported log covers it)."""
    for log in logs:
        if key in log.no_record:
            return {"recorded": False}
        names = [a for a, k in log.matched.items() if k == key]
        if not names:
            continue
        main = max(sorted(names), key=lambda a: log.activity_cases.get(a, 0))
        metrics = rows.get(f"{log.log_id}/{main}") or {}
        figures = log.step_figures.get(key, {})
        cases = int(figures.get("cases", 0))
        return {
            "recorded": True, "cases": cases, "rework_cases": int(figures.get("rework_cases", 0)),
            "time": _measure(metrics.get("work"), cases),  # type: ignore[arg-type]
            "wait_before": _measure(metrics.get("wait_before"), cases),  # type: ignore[arg-type]
            "log_id": log.log_id, "activity": main,
        }  # fmt: skip
    return {}


def _first(values: list[float | None]) -> float | None:
    return next((v for v in values if v is not None), None)


def _conditions(claims: Mapping[str, list[ClaimRecord]]) -> dict[str, str]:
    out = {}
    for element_id, cs in claims.items():
        text = next(
            (
                str(c.payload.get("variation_condition") or "").strip()
                for c in cs
                if c.account_type == "lived" and c.payload.get("variation_condition")
            ),
            "",
        )
        if text:
            out[element_id] = text
    return out  # fmt: skip


def _steps(session: Session, version: VersionView, done: Graph, documented: Graph,
           logs: list[LogFacts]) -> tuple[list[rules.StepFacts], dict[str, dict[str, object]],
                                          dict[str, Offsets]]:  # fmt: skip
    """Each step's facts, what the log says of it, and its (lived, documented) time offsets."""
    records = [
        e
        for e in map_repo.elements(session, version.id)
        if e.kind in STEP_KINDS and e.review_status != ReviewStatus.REJECTED.value
    ]
    in_done = {e.id for e in done.elements}
    in_documented = {e.id for e in documented.elements}
    graph: dict[str, GraphElement] = {e.id: e for e in [*documented.elements, *done.elements]}
    claims = _claims(session, version.id)
    kinds = {s.id: s.kind for s in sources_repo.list_for_engagement(session, version.engagement_id)}
    practice = _practice_interviews(session, version.engagement_id)
    usual = _usual_route(done, _conditions(claims))
    rows = {f"{log.log_id}/{r.key}": r.metrics for log in logs
            for r in logs_repo.metrics(session, log.log_id, "activity")}  # fmt: skip
    steps, systems, offsets = [], {}, {}
    for order, e in enumerate(records):
        g = graph.get(e.id)
        cs = claims.get(e.id, [])
        documents = [c for c in cs if kinds.get(c.source_id) in DOCUMENT_KINDS]
        interviews = [c for c in cs if kinds.get(c.source_id) == INTERVIEW]
        lived = [c for c in interviews if c.account_type == "lived"]
        variants = (g.variants if g else None) or {}
        documented_text = variants.get("documented", {}).get("time", "")
        documented_min = _first([stated_minutes(documented_text) if documented_text else None,
                                 *(stated_minutes(_words(c)) for c in documents)])  # fmt: skip
        offsets[e.stable_key] = (_first([_offset(_words(c)) for c in lived]),
                                 _first([_offset(_words(c)) for c in documents]))  # fmt: skip
        system = _system(e.stable_key, logs, rows)
        systems[e.stable_key] = system
        time = g.time if g else None
        steps.append(rules.StepFacts(
            key=e.stable_key, element_id=e.id, label=e.label, kind=e.kind, order=order,
            in_done=e.id in in_done, in_documented=e.id in in_documented,
            usual_route=e.id in usual, risk_flag=e.risk_flag or None,
            divergence_types=tuple(e.divergence_types),
            documented_owner=variants.get("documented", {}).get("owner", ""),
            done_owner=variants.get("done", {}).get("owner", ""),
            described_in=len({c.source_id for c in interviews
                              if c.source_id in practice and c.account_type != "official"}),
            lived_accounts=len(lived), documented_min=documented_min,
            done_min=time.work_min if time else None,
            stated_wait=time.wait_min if time else None,
            official_min=tuple(v for c in interviews if c.account_type == "official"
                               and (v := stated_minutes(_words(c))) is not None),
            tools=_tools(cs, kinds),
            recorded=system.get("recorded"),  # type: ignore[arg-type]
            cases=int(system.get("cases", 0)),  # type: ignore[call-overload]
            rework_cases=int(system.get("rework_cases", 0)),  # type: ignore[call-overload]
            time=system.get("time"),  # type: ignore[arg-type]
            wait_before=system.get("wait_before"),  # type: ignore[arg-type]
            artefact_support=any(kinds.get(c.source_id) == ARTEFACT for c in cs),
        ))  # fmt: skip
    return steps, systems, offsets


def _with_skips(steps: list[rules.StepFacts], lines: list[rules.Line]) -> list[rules.StepFacts]:
    """D1 (a) and D5: cases reaching the next documented step, and of those, cases without this
    step (the next step's recorded cases less this step's; every recorded case reaches it)."""
    by_key = {s.key: s for s in steps}
    out = []
    for s in steps:
        ahead = [ln.target for ln in lines if ln.source == s.key
                 and ln.kind not in rules.REWORK_LINES and ln.target in by_key]  # fmt: skip
        nxt = by_key[ahead[0]] if ahead else None
        if s.recorded and nxt is not None and nxt.recorded:
            s = dataclasses.replace(s, reach_next=nxt.cases, skipped=max(0, nxt.cases - s.cases))
        out.append(s)
    return out


def _lines(graph: Graph, keys: Mapping[str, str]) -> list[rules.Line]:
    return [rules.Line(keys[e.from_], keys[e.to], e.kind, e.sequence_basis or "")
            for e in graph.edges if e.from_ in keys and e.to in keys]  # fmt: skip


def _covered(i: IntentRecord, steps: list[rules.StepFacts], phases: Mapping[str, str],
             phase_of: Mapping[str, str | None]) -> tuple[str, ...]:  # fmt: skip
    """The step keys a statement covers: its step, its phase's steps, or none (the process)."""
    keys = {s.key for s in steps}
    if i.scope == "step" and i.element_stable_key in keys:
        return (str(i.element_stable_key),)
    if i.scope == "phase" and i.phase_name in phases:
        wanted = phases[str(i.phase_name)]
        return tuple(s.key for s in steps if phase_of.get(s.element_id) == wanted)
    return ()


def _within(
    session: Session, system: Mapping[str, object], target: evaluation.Target
) -> int | None:
    """Measured cases whose activity time meets the target (case by case)."""
    log_id, activity = system.get("log_id"), system.get("activity")
    if not isinstance(log_id, str) or not isinstance(activity, str):
        return None
    spans = logs_repo.activity_spans(session, log_id, activity)
    return sum(1 for a, b in spans if evaluation.meets(target, _minutes(a, b)))


def _values(session: Session, i: IntentRecord, target: evaluation.Target,
            step: rules.StepFacts | None, system: Mapping[str, object],
            offsets: Offsets, logs: list[LogFacts]) -> evaluation.Values:  # fmt: skip
    if i.metric in ("wait_min", "step_time_min") and step is not None:
        measured = rules.measured_wait(step) if i.metric == "wait_min" else step.time
        is_span = measured is not None and measured is step.time
        return evaluation.Values(
            measured=measured.median if measured else None,
            measured_cases=measured.cases if measured else 0,
            within=_within(session, system, target) if is_span else None,
            stated=step.stated_wait if i.metric == "wait_min" else step.done_min,
            documented=step.documented_min,
        )  # fmt: skip
    if i.metric == "lead_time_min" and step is not None:
        return evaluation.Values(stated=offsets[0], documented=offsets[1])
    if i.metric == "cycle_time_min" and logs:
        case = next(iter(logs_repo.metrics(session, logs[0].log_id, "case")), None)
        spread = (case.metrics.get("cycle_time") or {}) if case else {}
        median = spread.get("median_min") if isinstance(spread, dict) else None
        cases = case.case_count if case else 0
        return evaluation.Values(measured=float(median) if median is not None else None,
                                 measured_cases=cases)  # fmt: skip
    return evaluation.Values()


def gather(session: Session, version: VersionView) -> tuple[rules.Facts, list[IntentRecord]]:
    """The facts of one version for the discrepancy engine, and its confirmed statements."""
    done = versions_action.build_graph(session, version.id, every_line=True, view="done")
    documented = versions_action.build_graph(session, version.id, every_line=True,
                                             view="documented")  # fmt: skip
    assert done is not None and documented is not None
    logs = system_trace.log_facts_for(session, version)
    steps, systems, offsets = _steps(session, version, done, documented, logs)
    keys = {s.element_id: s.key for s in steps}
    done_lines, documented_lines = _lines(done, keys), _lines(documented, keys)
    steps = _with_skips(steps, documented_lines)
    by_key = {s.key: s for s in steps}
    phases = {p.name: p.id for p in done.phases}
    phase_of = {e.id: e.phase_id for e in map_repo.elements(session, version.id)}
    confirmed = [r for r in intent_repo.for_engagement(session, version.engagement_id)
                 if r.status == "confirmed"]  # fmt: skip
    intents = []
    for i in confirmed:
        covered = _covered(i, steps, phases, phase_of)
        if i.metric and i.comparator and i.target_value is not None:
            target = evaluation.Target(i.metric, i.comparator, float(i.target_value))
            first = covered[0] if covered else ""
            values = _values(session, i, target, by_key.get(first), systems.get(first, {}),
                             offsets.get(first, (None, None)), logs)  # fmt: skip
            result = evaluation.evaluate(target, values)
        else:
            result = evaluation.Evaluation(evaluation.UNKNOWN)
        intents.append(rules.IntentOnStep(
            intent_id=i.id, kind=i.kind, step_keys=covered, metric=i.metric,
            comparator=i.comparator, target=i.target_value, result=result.result,
            actual=result.actual, label=result.label, met_share=result.met_share,
            cases=result.cases, documented=result.documented,
            documented_meets=result.documented_meets,
        ))  # fmt: skip
    statements = {i.intent_id: i for i in intents}
    conflicts = [rules.DesignConflict(c.id, c.intent_id, statements[c.intent_id].step_keys,
                                      c.conflict_text)
                 for c in intent_repo.conflicts(session, version.id)
                 if c.status == "confirmed" and c.intent_id in statements]  # fmt: skip
    variants = sorted((r.case_count for r in logs_repo.metrics(session, logs[0].log_id, "variant")),
                      reverse=True) if logs else []  # fmt: skip
    facts = rules.Facts(
        steps=steps, done_lines=done_lines, documented_lines=documented_lines,
        hidden=[rules.HiddenWork(a, log.activity_cases.get(a, 0)) for log in logs
                for a in log.hidden],
        variants=variants, total_cases=max((log.cases for log in logs), default=0),
        interviews=len(_practice_interviews(session, version.engagement_id)),
        intents=intents, conflicts=conflicts,
        contradictions={k: v for log in logs for k, v in log.contradictions.items()},
    )  # fmt: skip
    return facts, confirmed


def _view(found: rules.Found, ids: Mapping[str, str]) -> DiscrepancyFound:
    return DiscrepancyFound(
        type=found.type, keys=list(found.keys),
        element_ids=[ids[k] for k in found.keys if k in ids],
        delta=DeltaView(value=found.delta.value, unit=found.delta.unit, label=found.delta.label,
                        text=found.delta.text),
        incidence=found.incidence, cases=found.cases, control=found.control, shown=found.shown,
        intent_ids=list(found.intent_ids), detail=dict(found.detail),
    )  # fmt: skip


def detection(session: Session, version: VersionView) -> Detection:
    """Every discrepancy on the version and every confirmed statement's evaluation."""
    facts, _ = gather(session, version)
    found = rules.detect(facts)
    ids = {s.key: s.element_id for s in facts.steps}
    evaluations = []
    for i in facts.intents:
        if i.metric is None:
            failures = [(f.type, f.incidence, f.cases) for f in found
                        if set(f.keys) & set(i.step_keys)]  # fmt: skip
            e = evaluation.evaluate_without_metric(i.kind, failures)
            evaluations.append(
                IntentEvaluationView(
                    intent_id=i.intent_id,
                    result=e.result,
                    actual=e.actual,
                    label=e.label,
                    met_share=e.met_share,
                    cases=e.cases,
                    documented=None,
                    documented_meets=None,
                )
            )
        else:
            evaluations.append(IntentEvaluationView(
                intent_id=i.intent_id, result=i.result, actual=i.actual, label=i.label,
                met_share=i.met_share, cases=i.cases, documented=i.documented,
                documented_meets=i.documented_meets))  # fmt: skip
    return Detection(
        rules_version=rules.REALITY_RULES_VERSION,
        discrepancies=[_view(f, ids) for f in found],
        intents=evaluations,
    )


def detect_for(sessions: Sessions, version_id: str) -> Result[Detection]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        return Ok(detection(session, version))
