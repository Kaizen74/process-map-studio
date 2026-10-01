"""S4b Translate (PRD §3.12.10 step C rules 1-7, §3.12.11): the two views of the assembled map.

Deterministic, no AI call. From each step's verified claims (where their passages sit, whether a
claim gives the lived account and confirmed an explicit-order marker) and its source state, every
step and line gets its view membership and every line its sequence basis. Where one view leaves
out the other view's steps, the line that view needs is added (provenance I: inferred by these
rules from the sources' order): in As documented a plain line; in
As done a line only when the lived account states the order, otherwise a "not described"
connector (kind `gap`), never an invented step. Lines resting only on the order of mentioning,
and "not described" connectors, become validation questions (`ask`, after S5's step questions).
Running either again changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import EdgeKind, Provenance, SourceKind
from app.domain.graph import EdgeRecord, QuestionRecord
from app.domain.models import ClaimRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import StepPosition, Translation, TranslationEdge, TranslationStep
from app.pipeline.context import AiContext
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import translation

Sessions = sessionmaker[Session]

DOCUMENTS = {SourceKind.SOP.value, SourceKind.MANUAL.value}
EXPLICIT = "explicit_order"
MISSING = "That version doesn't exist."


@dataclass(slots=True)
class S4bTally:
    added_lines: int = 0
    not_described: int = 0
    questions: int = 0


def _explicit(claim: ClaimRecord) -> bool:
    """The claim confirmed an explicit-order marker with a quote found in its passages (B3)."""
    markers = claim.payload.get("markers")
    return isinstance(markers, list) and any(
        isinstance(m, dict) and m.get("confirmed") and str(m.get("marker", "")).startswith(EXPLICIT)
        for m in markers
    )


def steps_for(session: Session, version_id: str) -> list[TranslationStep]:
    """Each element with where its verified claims sit in their sources."""
    elements = map_repo.elements(session, version_id)
    linked = map_repo.element_claims(session, version_id)
    claims = claims_repo.by_ids(session, [c for ids in linked.values() for c in ids])
    segment_ids = [s for c in claims.values() for s in c.segment_ids]
    rows = sources_repo.segment_rows(session, segment_ids)
    owners = sources_repo.segment_owners(session, segment_ids)
    steps = []
    for e in elements:
        interview: list[StepPosition] = []
        documents: list[StepPosition] = []
        for claim_id in linked.get(e.id, []):
            claim = claims.get(claim_id)
            if claim is None or claim.verification_status != "verified":
                continue
            seqs = [rows[s][0].seq for s in claim.segment_ids if s in rows]
            kinds = {owners[s][2] for s in claim.segment_ids if s in owners}
            if not seqs:
                continue
            if SourceKind.INTERVIEW_TRANSCRIPT.value in kinds:
                interview.append(StepPosition(
                    source_id=claim.source_id, seq=min(seqs),
                    lived=claim.account_type == "lived", explicit=_explicit(claim),
                ))  # fmt: skip
            elif kinds & DOCUMENTS:
                documents.append(StepPosition(source_id=claim.source_id, seq=min(seqs)))
        steps.append(TranslationStep(
            id=e.id, kind=e.kind, label=e.label, source_state=e.source_state,
            provenance=e.provenance, interview=interview, documents=documents,
            handoff_in=e.handoff_in, handoff_out=e.handoff_out,
        ))  # fmt: skip
    return steps


def _translation(session: Session, version_id: str) -> Translation | None:
    steps = steps_for(session, version_id)
    if not steps:
        return None
    return translation.translate(steps, [
        TranslationEdge(id=e.id, from_id=e.from_element_id, to_id=e.to_element_id,
                        kind=e.kind, label=e.label)
        for e in map_repo.edges(session, version_id)
    ])  # fmt: skip


def translate(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S4bTally]:
    """Views and sequence basis on every step and line; the lines each view needs added."""
    tally = S4bTally()
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, MISSING)
        result = _translation(session, version_id)
        if result is None:
            return Ok(tally)
        for element_id, view in result.element_views.items():
            map_repo.update_element(session, element_id, {"view_membership": view})
        added = []
        for edge in result.edges:
            if edge.id is not None:
                map_repo.update_edge(session, edge.id, {
                    "sequence_basis": edge.sequence_basis,
                    "view_membership": edge.view_membership,
                })  # fmt: skip
                continue
            added.append(EdgeRecord(
                from_element_id=edge.from_id, to_element_id=edge.to_id, kind=edge.kind,
                label=edge.label, provenance=Provenance.INFERRED.value,
                sequence_basis=edge.sequence_basis, view_membership=edge.view_membership,
            ))  # fmt: skip
            tally.added_lines += 1
            tally.not_described += edge.kind == EdgeKind.GAP.value
        map_repo.add_edges(session, version_id, added)
    return Ok(tally)


def ask(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S4bTally]:
    """The translation's validation questions (order not stated; not described), written after
    the step questions of S5 and never twice."""
    tally = S4bTally()
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, MISSING)
        result = _translation(session, version_id)
        if result is None:
            return Ok(tally)
        phases = {e.id: e.phase_id for e in map_repo.elements(session, version_id)}
        asked = {(q.element_id, q.question) for q in map_repo.questions(session, version_id)}
        new = [
            QuestionRecord(element_id=q.element_id, phase_id=phases.get(q.element_id),
                           question=q.question, reason=q.reason)
            for q in result.questions
            if (q.element_id, q.question) not in asked
        ]  # fmt: skip
        map_repo.add_questions(session, version_id, new)
        tally.questions = len(new)
    return Ok(tally)
