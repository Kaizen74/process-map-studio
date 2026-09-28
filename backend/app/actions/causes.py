"""The cause library (PRD §3.5 `cause_library`, §6.3 P9; API_CONTRACT.md → Cause library).

When a draft is made or refreshed, each contested or trace-contradicted step gets one entry per
divergence type, pending Eric's validation. The pattern is the observed divergence (the notes on
the step's contradicting evidence); a cause is filled in only from a constraint recorded on the
same step with a cause type, and is otherwise left empty ("not known yet: ask your SME"). No AI
call and no guess (constraint 1). Entries are engagement-level and are never added twice.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, Provenance, ReviewStatus, SourceState, Stance
from app.domain.graph import GraphElement
from app.domain.models import CausePatch, CauseRecord, CauseView, NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import causes as repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]

CAUSE_MISSING = "That cause-library entry doesn't exist."
BAD_RESULT = "Choose pending, confirmed or refuted."
RESULTS = {"pending": "Reopened cause", "confirmed": "Confirmed cause", "refuted": "Refuted cause"}
DIVERGING = {SourceState.CONTESTED.value, SourceState.TRACE_CONTRADICTED.value}
STEPS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}


def _pattern(element: GraphElement) -> str:
    """The observed divergence: the notes on the step's contradicting evidence, in order."""
    notes = [
        e.note for e in element.evidence if e.stance == Stance.CONTRADICTS.value and e.note.strip()
    ]
    unique = list(dict.fromkeys(notes))
    return "; ".join(unique) if unique else f"The sources disagree about “{element.label}”."


def _cause(element: GraphElement) -> tuple[str, str]:
    """(cause, cause type) from the step's own constraints with a cause type, key ones first."""
    typed = [c for c in element.constraints if c.cause_type]
    typed.sort(key=lambda c: not c.is_key)
    return (typed[0].text, typed[0].cause_type or "") if typed else ("", "")


def collect(session: Session, version_id: str) -> int:
    """Add the entries for the version's contested and trace-contradicted steps; returns how many
    were added. Existing entries (and Eric's validation of them) are kept."""
    graph = versions_action.build_graph(session, version_id)
    version = versions_repo.get(session, version_id)
    if graph is None or version is None:
        return 0
    known = repo.keys(session, version.engagement_id)
    added = 0
    for element in graph.elements:
        if (
            element.kind not in STEPS
            or element.review_status == ReviewStatus.REJECTED.value
            or element.source_state not in DIVERGING
        ):
            continue
        cause, cause_type = _cause(element)
        for divergence in element.divergence_types or [""]:
            if (element.stable_key, divergence) in known:
                continue
            repo.add(
                session,
                CauseRecord(
                    engagement_id=version.engagement_id,
                    element_stable_key=element.stable_key,
                    divergence_type=divergence,
                    pattern=_pattern(element),
                    inferred_cause=cause,
                    cause_type=cause_type,
                    # The pattern is observed; a cause linked to it is an inference to validate.
                    provenance=Provenance.INFERRED.value if cause else Provenance.OBSERVED.value,
                ),
            )
            known.add((element.stable_key, divergence))
            added += 1
    return added


def _views(session: Session, engagement_id: str, records: list[CauseRecord]) -> list[CauseView]:
    terms: list[NameReplacement] = redaction.name_replacements(session, engagement_id)
    map_id = versions_repo.current_map_id(session, engagement_id)
    current = {e.stable_key: e for e in (map_repo.elements(session, map_id) if map_id else [])}
    labels = repo.last_labels(session, engagement_id)
    views = []
    for r in records:
        step = current.get(r.element_stable_key)
        label = step.label if step else labels.get(r.element_stable_key, "")
        views.append(
            CauseView(
                id=r.id,
                element_stable_key=r.element_stable_key,
                element_id=step.id if step else None,
                element_label=redaction.hide(label, terms),
                divergence_type=r.divergence_type,
                pattern=redaction.hide(r.pattern, terms),
                inferred_cause=redaction.hide(r.inferred_cause, terms),
                cause_type=r.cause_type or None,
                provenance=r.provenance,
                validation_result=r.validation_result,
                created_at=r.created_at,
            )
        )
    return views


def list_causes(sessions: Sessions, engagement_id: str) -> Result[list[CauseView]]:
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(_views(session, engagement_id, repo.for_engagement(session, engagement_id)))


def validate(
    config: AppConfig, sessions: Sessions, cause_id: str, patch: CausePatch
) -> Result[CauseView]:
    """Eric confirms or refutes an entry (or reopens it); one audit row."""
    if patch.validation_result not in RESULTS:
        return Err(ErrorKind.VALIDATION, BAD_RESULT, {"field": "validation_result"})
    with session_scope(sessions) as session:
        before = repo.get(session, cause_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, CAUSE_MISSING)
        after = repo.set_validation(session, cause_id, patch.validation_result)
        if before.validation_result != after.validation_result:
            audit.record(
                session,
                actor=actor_name(config),
                action=RESULTS[after.validation_result],
                target_type="cause",
                target_id=cause_id,
                engagement_id=after.engagement_id,
                version_id=versions_repo.current_map_id(session, after.engagement_id),
                before={"validation_result": before.validation_result},
                after={"validation_result": after.validation_result},
            )
        return Ok(_views(session, after.engagement_id, [after])[0])
