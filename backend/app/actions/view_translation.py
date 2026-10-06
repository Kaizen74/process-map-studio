"""The As done and As documented views of a version's map (PRD §3.12.10 rules 1 and 7,
§3.12.11), kept up to date: after the draft is assembled and after every edit Eric makes to the
map. Deterministic, no AI call; the rules are in `services/translation.py`.

Each step's verified claims give where it sits in its sources (lived or not, explicit-order
marker confirmed or not); the rules give every step and line its view membership and every line
its sequence basis, and add the lines a view needs where it leaves out the other view's steps
(provenance I). Running it again changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.enums import EdgeKind, Provenance, ReviewStatus, SourceKind
from app.domain.graph import EdgeRecord, QuestionRecord
from app.domain.models import ClaimRecord
from app.domain.sensemaking import StepPosition, Translation, TranslationEdge, TranslationStep
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.services import translation
from app.services.views import added_by_translation

DOCUMENTS = {SourceKind.SOP.value, SourceKind.MANUAL.value}
EXPLICIT = "explicit_order"


@dataclass(slots=True)
class Tally:
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
    """Each element with where its verified claims sit in their sources, and the information it
    passes on and receives (the decision-information items S3c linked to it; rule 8)."""
    elements = map_repo.elements(session, version_id)
    linked = map_repo.element_claims(session, version_id)
    claims = claims_repo.by_ids(session, [c for ids in linked.values() for c in ids])
    segment_ids = [s for c in claims.values() for s in c.segment_ids]
    rows = sources_repo.segment_rows(session, segment_ids)
    owners = sources_repo.segment_owners(session, segment_ids)
    gives: dict[str, list[str]] = {}
    takes: dict[str, list[str]] = {}
    for _, item in claims_repo.verified_rows(session, version_id):
        about = item.payload.get("about_steps")
        if item.claim_type != "decision_info" or not isinstance(about, list):
            continue
        sent, got = item.payload.get("communicated_via"), item.payload.get("received")
        for key in about:
            gives.setdefault(str(key), []).extend(map(str, sent if isinstance(sent, list) else []))
            takes.setdefault(str(key), []).extend(map(str, got if isinstance(got, list) else []))
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
                questions = [rows[s][0].question_id for s in claim.segment_ids if s in rows]
                interview.append(StepPosition(
                    source_id=claim.source_id, seq=min(seqs),
                    lived=claim.account_type == "lived", explicit=_explicit(claim),
                    question_ids=[q for q in questions if q],
                ))  # fmt: skip
            elif kinds & DOCUMENTS:
                documents.append(StepPosition(source_id=claim.source_id, seq=min(seqs)))
        steps.append(TranslationStep(
            id=e.id, kind=e.kind, label=e.label, source_state=e.source_state,
            provenance=e.provenance, interview=interview, documents=documents,
            handoff_in=e.handoff_in, handoff_out=e.handoff_out,
            added_by_owner=e.review_status == ReviewStatus.ADDED.value,
            lane=e.lane_role_id or "", phase=e.phase_id or "", gives=gives.get(e.stable_key, []),
            takes=takes.get(e.stable_key, []),
        ))  # fmt: skip
    return steps


def _translation(
    session: Session, version_id: str, steps: list[TranslationStep]
) -> Translation | None:
    if not steps:
        return None
    return translation.translate(steps, [
        TranslationEdge(id=e.id, from_id=e.from_element_id, to_id=e.to_element_id,
                        kind=e.kind, label=e.label)
        for e in map_repo.edges(session, version_id)
    ])  # fmt: skip


def update_views(session: Session, version_id: str) -> Tally:
    """Views and sequence basis on every step and line; the lines each view needs added. The
    lines added last time are worked out again from the lines as they are now (so a relabelled
    exit or a new step is reflected); a line Eric has edited is his and stays."""
    tally = Tally()
    for stored in map_repo.edges(session, version_id):
        if added_by_translation(stored.provenance, stored.view_membership):
            map_repo.delete_edge(session, stored.id)
    steps = steps_for(session, version_id)
    # Rule 9 (K2): levels and parents, worked out again like the views; both None on a map with
    # one level.
    for element_id, (level, parent) in translation.levels(steps).items():
        map_repo.update_element(session, element_id, {"level": level, "parent_element_id": parent})
    result = _translation(session, version_id, steps)
    if result is None:
        return tally
    for element_id, view in result.element_views.items():
        map_repo.update_element(session, element_id, {"view_membership": view})
    added: list[EdgeRecord] = []
    for edge in result.edges:
        if edge.id is not None:
            map_repo.update_edge(session, edge.id, {
                "sequence_basis": edge.sequence_basis, "view_membership": edge.view_membership,
                "information_payload": edge.information_payload,
            })  # fmt: skip
            continue
        added.append(EdgeRecord(
            from_element_id=edge.from_id, to_element_id=edge.to_id, kind=edge.kind,
            label=edge.label, provenance=Provenance.INFERRED.value,
            sequence_basis=edge.sequence_basis, view_membership=edge.view_membership,
            information_payload=edge.information_payload,
        ))  # fmt: skip
        tally.added_lines += 1
        tally.not_described += edge.kind == EdgeKind.GAP.value
    map_repo.add_edges(session, version_id, added)
    return tally


def add_questions(session: Session, version_id: str) -> int:
    """The translation's validation questions (order not stated; not described), never twice
    (a question already asked, open or answered, is not asked again)."""
    result = _translation(session, version_id, steps_for(session, version_id))
    if result is None:
        return 0
    phases = {e.id: e.phase_id for e in map_repo.elements(session, version_id)}
    asked = {(q.reason, q.question) for q in map_repo.questions(session, version_id)}
    new = [
        QuestionRecord(element_id=q.element_id, phase_id=phases.get(q.element_id),
                       question=q.question, reason=q.reason)
        for q in result.questions
        if (q.reason, q.question) not in asked
    ]  # fmt: skip
    map_repo.add_questions(session, version_id, new)
    return len(new)
