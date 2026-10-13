"""Step disposition (API_CONTRACT.md → Step disposition; PRD §3.15; criterion 91; R9a).

The suggestion is worked out on every read from the step as it is now (no AI, nothing stored);
Eric's choice is stored on the step, audited, and kept across reopen and refresh.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, ReviewStatus, VersionState
from app.domain.graph import GraphElement
from app.domain.models import DispositionInput, DispositionView, RefusedDisposition, VersionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import event_logs as logs_repo
from app.repositories import gap as gap_repo
from app.repositories import versions as versions_repo
from app.services import disposition as rules
from app.services import grounding
from app.services.disposition import StepFacts

Sessions = sessionmaker[Session]

NOT_STEPS = {ElementKind.START.value, ElementKind.END.value}
VERSION_MISSING = versions_action.VERSION_MISSING
ELEMENT_MISSING = versions_action.ELEMENT_MISSING
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
NOT_A_STEP = "The start and the end have no disposition."
BAD_RISK = "Choose none, financial, safety or regulatory."
BAD_NOTE = "Keep the note to one line of up to 300 characters."
HIDDEN_NAME = "The note contains a name from your list of names to hide. Use the role instead."
HEURISTIC = {"heuristics", "experience"}


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _unrecorded(session: Session, engagement_id: str) -> dict[str, str]:
    """Steps (by stable key) Eric confirmed have no system record, with the log's name."""
    out: dict[str, str] = {}
    for log in logs_repo.list_for(session, engagement_id):
        if log.status != "imported":
            continue
        for row in logs_repo.alignment(session, log.id):
            if row.confirmed and row.status == "no_system_record" and row.step_key:
                out.setdefault(row.step_key, log.name)
    return out


def _flag(element: GraphElement) -> dict[str, str] | None:
    f = element.ai_flag
    if f is None:
        return None
    return {"component": f.component, "input": f.input, "output": f.output,
            "handoff": f.handoff, "basis": f.basis}  # fmt: skip


def facts(session: Session, version: VersionView) -> dict[str, tuple[GraphElement, StepFacts]]:
    """Every step of the version (start, end and rejected steps left out) with its facts."""
    graph = versions_action.build_graph(session, version.id)
    if graph is None:
        return {}
    records = {r.id: r for r in map_repo.elements(session, version.id)}
    unrecorded = _unrecorded(session, version.engagement_id)
    lens = lenses.load(session, version.id, version.engagement_id)
    terms = redaction.name_replacements(session, version.engagement_id)
    out: dict[str, tuple[GraphElement, StepFacts]] = {}
    for e in graph.elements:
        record = records.get(e.id)
        if e.kind in NOT_STEPS or record is None or e.review_status == ReviewStatus.REJECTED.value:
            continue
        know = lenses.know_how(lens, record.stable_key, e.kind, e.work_type)
        items = {k: len(v) for k, v in (know.ashen.items() if know else [])}
        total = sum(items.values())
        findings = [
            (f.finding_type, f.gap_class, redaction.hide(f.title, terms))
            for _, f in gap_repo.step_findings(session, version.engagement_id, record.stable_key)
            if f.disposition != "dismissed"
        ]
        out[e.id] = (e, StepFacts(
            label=e.label, kind=e.kind, work_type=e.work_type, mechanism=e.decision.mechanism,
            flag=_flag(e), risk_flag=record.risk_flag or "none", source_state=e.source_state,
            has_purpose=bool(e.kpi.strip() or e.constraints),
            no_record_in=unrecorded.get(record.stable_key, ""),
            knowledge_risk=know.knowledge_risk if know else "unknown",
            heuristics_share=sum(items.get(k, 0) for k in HEURISTIC) / total if total else 0.0,
            findings=findings,
        ))  # fmt: skip
    return out


def _view(element: GraphElement, step: StepFacts, chosen: str | None,
          note: str) -> DispositionView:  # fmt: skip
    suggested, reason = rules.suggest(step)
    return DispositionView(
        element_id=element.id, label=element.label, kind=element.kind, suggested=suggested,
        reason=reason, disposition=chosen, note=note, risk_flag=step.risk_flag,
        allowed=rules.allowed(step),
        not_allowed=[RefusedDisposition(disposition=d, reason=why)
                     for d in rules.ALL if (why := rules.refusal(step, d))],
    )  # fmt: skip


def views(session: Session, version: VersionView) -> list[DispositionView]:
    records = {r.id: r for r in map_repo.elements(session, version.id)}
    return [_view(e, f, records[i].disposition, records[i].disposition_note or "")
            for i, (e, f) in facts(session, version).items()]  # fmt: skip


def get_dispositions(sessions: Sessions, version_id: str) -> Result[list[DispositionView]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        return Ok(views(session, version))


def set_disposition(config: AppConfig, sessions: Sessions, element_id: str,
                    body: DispositionInput) -> Result[DispositionView]:  # fmt: skip
    note = body.note.strip()
    if len(note) > 300 or "\n" in note:
        return _invalid("note", BAD_NOTE)
    if "risk_flag" in body.model_fields_set and body.risk_flag not in rules.RISK_FLAGS:
        return _invalid("risk_flag", BAD_RISK)
    actor = actor_name(config)
    with session_scope(sessions) as session:
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        record = map_repo.element(session, element_id)
        if version is None or record is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if version.state != VersionState.DRAFT.value:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if record.kind in NOT_STEPS:
            return _invalid("element_id", NOT_A_STEP)
        terms = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
        if note and grounding.scan_redaction_terms(note, terms):
            return _invalid("note", HIDDEN_NAME)
        found = facts(session, version).get(element_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        element, step = found
        if "risk_flag" in body.model_fields_set:
            step = replace(step, risk_flag=body.risk_flag or "none")
        if body.disposition is not None and (why := rules.refusal(step, body.disposition)):
            return _invalid("disposition", why)
        suggested, _ = rules.suggest(step)
        before = {"disposition": record.disposition, "note": record.disposition_note or "",
                  "risk_flag": record.risk_flag or "none"}  # fmt: skip
        after = {"disposition": body.disposition, "note": note, "risk_flag": step.risk_flag}
        if before != after:
            map_repo.update_element(session, element_id, {
                "disposition": body.disposition, "disposition_note": note or None,
                "risk_flag": step.risk_flag,
            })  # fmt: skip
            audit.record(
                session, actor=actor, action="Chose disposition", target_type="element",
                target_id=element_id, engagement_id=version.engagement_id, version_id=version.id,
                before=before, after={**after, "suggested": suggested},
            )  # fmt: skip
        view = _view(element, step, body.disposition, note)
    versions_action.lint_version(sessions, version.id)
    return Ok(view)
