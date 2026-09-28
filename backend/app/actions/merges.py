"""Merge decisions (PRD §5.7.10 Merge tab, §9 assumption 8; phase P6).

S2 proposes steps that may be one step described differently. Below 0.80 similarity the steps
stay separate until Eric decides; at 0.80 or above they are merged while drafting and listed as
accepted. Here Eric accepts a merge (the separate steps become one), keeps the steps separate, or
splits a merge back into the steps S2 drafted. Constraint 3 ("don't reconcile") is kept: a merge
joins claims and evidence, it never picks one source's account over another. Reviewed steps are
never merged or split; every merged or split step needs a check and has no confidence until the
next refresh works it out again.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.map_edits import insert_after
from app.actions.review import DRAFT_STATE, NOT_A_DRAFT
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import (
    DecisionMechanism,
    ElementKind,
    MergeDecision,
    Provenance,
    RaciLetter,
    ReviewStatus,
    Stance,
)
from app.domain.graph import (
    ElementRecord,
    EvidenceRecord,
    MergeGroup,
    MergeProposalRecord,
    RaciRecord,
)
from app.domain.models import (
    MergeClaimView,
    MergeGroupView,
    MergeProposalView,
    StanceFact,
    VersionView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.s2_canonicalise import stable_key
from app.repositories import audit
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import calibration, parsing

Sessions = sessionmaker[Session]

PROPOSAL_MISSING = "That merge proposal doesn't exist."
REVIEWED = (
    "One of these steps has already been reviewed. Change it with Edit, Reject or Add step instead."
)
IN_PLACE = "These steps are merged. Use Split to separate them again."
NO_GROUPS = (
    "This merge can't be split: its separate steps weren't recorded when it was drafted. "
    "Use Add step to put them back."
)
DECISIONS = {
    MergeDecision.ACCEPTED.value: "Accepted merge",
    MergeDecision.REJECTED.value: "Kept steps separate",
    MergeDecision.SPLIT.value: "Split merged step",
}
EDGE_KEY = tuple[str, str, str]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _owners(session: Session, version_id: str) -> dict[str, str]:
    """Claim ID → the element it currently belongs to."""
    return {c: e for e, cs in map_repo.element_claims(session, version_id).items() for c in cs}


def _view(session: Session, version: VersionView, p: MergeProposalRecord) -> MergeProposalView:
    terms = redaction.name_replacements(session, version.engagement_id)

    def hide(text: str) -> str:
        return redaction.hide(text, terms)

    owners = _owners(session, version.id)
    roles = {r.id: r.name for r in engagements_repo.list_roles(session, version.engagement_id)}
    claims = claims_repo.claims_by_id(session, p.claim_ids)
    names = {
        s.id: s.filename for s in sources_repo.list_for_engagement(session, version.engagement_id)
    }
    segments = sources_repo.segment_rows(
        session, [s for c in claims.values() for s in c.segment_ids]
    )
    groups = p.claim_groups
    if not groups:  # proposals from before groups were recorded: one side per current step
        by_element: dict[str, list[str]] = {}
        for c in p.claim_ids:
            by_element.setdefault(owners.get(c, ""), []).append(c)
        groups = [
            MergeGroup(
                label=str(claims[ids[0]].payload.get("text", "")) if ids[0] in claims else "",
                kind="",
                claim_ids=ids,
            )
            for ids in by_element.values()
        ]

    def anchor(claim_id: str) -> str:
        record = claims.get(claim_id)
        if record is None or not record.segment_ids:
            return ""
        row = segments.get(record.segment_ids[0])
        if row is None:
            return ""
        seg, fmt = row
        return parsing.segment_anchor(fmt=fmt, seq=seg.seq, page=seg.page, section=seg.section,
                                      text=seg.text, start_ms=seg.start_ms)  # fmt: skip

    merged = {owners.get(c) for c in p.claim_ids} - {None}
    return MergeProposalView(
        id=p.id,
        proposed_label=hide(p.proposed_label),
        similarity=p.similarity,
        decision=p.decision,
        decided_at=p.decided_at,
        element_id=next(iter(merged)) if len(merged) == 1 else None,
        groups=[
            MergeGroupView(
                label=hide(g.label),
                kind=g.kind,
                lane_role_name=roles.get(g.lane_role_id or "", ""),
                element_id=(
                    next(iter(own))
                    if len(own := {owners.get(c) for c in g.claim_ids} - {None}) == 1
                    and len(merged) > 1
                    else None
                ),
                claims=[
                    MergeClaimView(
                        text=hide(str(claims[c].payload.get("text", ""))),
                        source_name=hide(names.get(claims[c].source_id, "")),
                        anchor=anchor(c),
                        quote=hide(claims[c].quote),
                    )
                    for c in g.claim_ids
                    if c in claims
                ],
            )
            for g in groups
        ],
    )


def list_proposals(sessions: Sessions, version_id: str) -> Result[list[MergeProposalView]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        return Ok(
            [_view(session, version, p) for p in map_repo.merge_proposals(session, version_id)]
        )


# --- Deciding -----------------------------------------------------------------------------------


def _source_state(session: Session, version_id: str, element: ElementRecord) -> str:
    """Worked out again from the element's evidence (silence is the absence of a stance)."""
    stances = [
        StanceFact(source_id=p.source_id, source_kind=p.evidence.source_kind,
                   stance=p.evidence.stance)
        for p in map_repo.evidence(session, version_id)
        if p.evidence.element_id == element.id and p.evidence.stance != Stance.SILENT.value
    ]  # fmt: skip
    return calibration.assign_source_state(stances, element.provenance)


def _merge(session: Session, version_id: str, p: MergeProposalRecord) -> Result[list[str]]:
    """Join the proposal's separate steps into the first; returns the IDs of the steps joined."""
    order = [e.id for e in map_repo.elements(session, version_id)]
    elements = {e.id: e for e in map_repo.elements(session, version_id)}
    owners = _owners(session, version_id)
    steps = sorted({owners[c] for c in p.claim_ids if c in owners}, key=order.index)
    if len(steps) < 2:
        return Ok(steps)
    if any(elements[s].review_status != ReviewStatus.DRAFT.value for s in steps):
        return Err(ErrorKind.CONFLICT, REVIEWED)
    keep, others = steps[0], steps[1:]
    claims = map_repo.element_claims(session, version_id)
    moved = [c for o in others for c in claims.get(o, [])]
    map_repo.unlink_claims(session, moved)
    map_repo.link_claims(session, keep, moved)
    links = [x.evidence.id for x in map_repo.evidence(session, version_id)
             if x.evidence.element_id in others]  # fmt: skip
    map_repo.move_evidence(session, links, keep)
    map_repo.move_questions(session, others, keep)
    seen: set[EDGE_KEY] = set()
    for edge in map_repo.edges(session, version_id):
        start = keep if edge.from_element_id in others else edge.from_element_id
        end = keep if edge.to_element_id in others else edge.to_element_id
        key = (start, end, edge.kind)
        if start == end or key in seen:
            map_repo.delete_edge(session, edge.id)
            continue
        seen.add(key)
        if (start, end) != (edge.from_element_id, edge.to_element_id):
            map_repo.update_edge(session, edge.id, {"from_element_id": start, "to_element_id": end})
    divergences = list(dict.fromkeys(d for s in steps for d in elements[s].divergence_types))
    map_repo.delete_elements(session, others)
    kept = elements[keep]
    map_repo.update_element(
        session,
        keep,
        {"label": p.proposed_label, "divergence_types": divergences, "needs_check": True,
         "confidence": None, "confidence_breakdown": []},
    )  # fmt: skip
    map_repo.update_element(
        session, keep, {"source_state": _source_state(session, version_id, kept)}
    )
    return Ok(steps)


def _split(session: Session, version: VersionView, p: MergeProposalRecord) -> Result[list[str]]:
    """Put a merged step back into the separate steps S2 drafted; returns their IDs."""
    version_id = version.id
    owners = _owners(session, version_id)
    merged = sorted({owners[c] for c in p.claim_ids if c in owners})
    if len(merged) != 1:
        return Ok(merged)  # already separate
    if len(p.claim_groups) < 2:
        return Err(ErrorKind.CONFLICT, NO_GROUPS)
    element = map_repo.element(session, merged[0])
    assert element is not None
    if element.review_status != ReviewStatus.DRAFT.value:
        return Err(ErrorKind.CONFLICT, REVIEWED)
    claims = claims_repo.claims_by_id(session, p.claim_ids)
    evidence = [x for x in map_repo.evidence(session, version_id)
                if x.evidence.element_id == element.id]  # fmt: skip
    first, rest = p.claim_groups[0], p.claim_groups[1:]
    first_segments = {s for c in first.claim_ids if c in claims for s in claims[c].segment_ids}
    taken = map_repo.stable_keys(session, version_id)
    roles = {r.id for r in engagements_repo.list_roles(session, version.engagement_id)}
    ids, previous = [element.id], element.id
    for group in rest:
        lane = group.lane_role_id if group.lane_role_id in roles else element.lane_role_id
        observed = any(claims[c].provenance == Provenance.OBSERVED.value
                       for c in group.claim_ids if c in claims)  # fmt: skip
        deciding = group.kind in {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
        [new] = map_repo.add_elements(session, version_id, [ElementRecord(
            stable_key=stable_key(group.label, taken), kind=group.kind, label=group.label,
            lane_role_id=lane, phase_id=element.phase_id,
            decision_mechanism=DecisionMechanism.JUDGMENT.value if deciding
            else DecisionMechanism.NONE.value,
            decider_role_id=lane if deciding else None,
            provenance=Provenance.OBSERVED.value if observed else Provenance.INFERRED.value,
            needs_check=True,
        )])  # fmt: skip
        mine = [c for c in group.claim_ids if c in claims]
        map_repo.unlink_claims(session, mine)
        map_repo.link_claims(session, new.id, mine)
        # The stances were judged against the joined step; the split step's evidence is what
        # its own verified claims cite, each supporting it.
        segments = list(dict.fromkeys(s for c in mine for s in claims[c].segment_ids))
        map_repo.delete_evidence(
            session,
            [x.evidence.id for x in evidence
             if x.evidence.segment_id in set(segments) - first_segments],
        )  # fmt: skip
        map_repo.add_evidence(session, _supports(session, new.id, segments))
        if lane:
            letters = (
                [RaciLetter.RESPONSIBLE.value] if group.kind == ElementKind.ACTIVITY.value else []
            )
            entries = [
                RaciRecord(element_id=new.id, role_id=lane, letter=x)
                for x in [*letters, RaciLetter.ACCOUNTABLE.value]
            ]
            map_repo.add_raci(session, entries)
        insert_after(session, version_id, previous, new.id)
        map_repo.update_element(
            session, new.id, {"source_state": _source_state(session, version_id, new)}
        )
        ids.append(new.id)
        previous = new.id
    map_repo.update_element(
        session,
        element.id,
        {"label": first.label, "needs_check": True, "confidence": None, "confidence_breakdown": [],
         "divergence_types": []},
    )  # fmt: skip
    map_repo.update_element(
        session, element.id, {"source_state": _source_state(session, version_id, element)}
    )
    return Ok(ids)


def _supports(session: Session, element_id: str, segment_ids: list[str]) -> list[EvidenceRecord]:
    owners = sources_repo.segment_owners(session, segment_ids)
    return [
        EvidenceRecord(element_id=element_id, segment_id=sid, source_kind=owners[sid][2],
                       stance=Stance.SUPPORTS.value, verified=True)
        for sid in segment_ids
        if sid in owners
    ]  # fmt: skip


def decide(
    config: AppConfig, sessions: Sessions, proposal_id: str, decision: str
) -> Result[MergeProposalView]:
    if decision not in DECISIONS:
        return Err(
            ErrorKind.VALIDATION,
            "Choose Accept merge, Keep separate or Split.",
            {"field": "decision"},
        )
    actor = actor_name(config)
    with session_scope(sessions) as session:
        found = map_repo.merge_proposal(session, proposal_id)
        version = versions_repo.get(session, found[0]) if found else None
        if found is None or version is None:
            return Err(ErrorKind.NOT_FOUND, PROPOSAL_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        proposal = found[1]
        if proposal.decision == decision:
            return Ok(_view(session, version, proposal))
        match decision:
            case MergeDecision.ACCEPTED.value:
                outcome = _merge(session, version.id, proposal)
            case MergeDecision.REJECTED.value if proposal.decision == MergeDecision.ACCEPTED.value:
                outcome = Err(ErrorKind.CONFLICT, IN_PLACE)
            case MergeDecision.REJECTED.value:
                outcome = Ok([])
            case _:
                if proposal.decision != MergeDecision.ACCEPTED.value:
                    outcome = Err(ErrorKind.CONFLICT, "Only merged steps can be split.")
                else:
                    outcome = _split(session, version, proposal)
        if isinstance(outcome, Err):
            session.rollback()
            return outcome
        updated = map_repo.set_merge_decision(session, proposal_id, decision, _now())
        audit.record(
            session,
            actor=actor,
            action=DECISIONS[decision],
            target_type="merge_proposal",
            target_id=proposal_id,
            engagement_id=version.engagement_id,
            version_id=version.id,
            before={"decision": proposal.decision},
            after={"decision": decision, "steps": outcome.value},
        )
    versions_action.lint_version(sessions, version.id)
    with session_scope(sessions) as session:
        return Ok(_view(session, version, updated))
