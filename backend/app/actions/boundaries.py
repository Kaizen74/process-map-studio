"""Lane-boundary findings (API_CONTRACT.md → GET /versions/{vid}/lane-boundaries; PRD F.4 L5,
F.6 F1 and F4, criterion 76; C8): each step of the map with its lane role and its checked claims
(the role each names as doing the work, the guide question its passage answers), names hidden,
handed to `services.boundaries`. Deterministic; never changes the map."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction, versions
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import BoundaryClaim, BoundaryStep, LaneBoundaryFinding
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import boundaries, grounding
from app.services.alignment import STEPS

Sessions = sessionmaker[Session]


def steps_for(session: Session, version_id: str) -> list[BoundaryStep] | None:
    """The map's steps in process order, each with its lane role and its verified claims."""
    version = versions_repo.get(session, version_id)
    graph = versions.build_graph(session, version_id) if version else None
    if version is None or graph is None:
        return None
    terms = redaction.name_replacements(session, version.engagement_id)
    roles = engagements_repo.list_roles(session, version.engagement_id)
    canonical = {grounding.normalise_text(n): r.name for r in roles for n in (r.name, *r.aliases)}
    lanes = {r.id: r.name for r in graph.roles}
    claims_of = map_repo.element_claims(session, version_id)
    records = claims_repo.by_ids(session, [c for ids in claims_of.values() for c in ids])
    records = {k: r for k, r in records.items() if r.verification_status == "verified"}
    firsts = [r.segment_ids[0] for r in records.values() if r.segment_ids]
    asked = {sid: seg.question_id or "" for sid, (seg, _) in
             sources_repo.segment_rows(session, firsts).items()}  # fmt: skip

    def role_of(name: str) -> str:
        if not name.strip():
            return ""
        return canonical.get(grounding.normalise_text(name), redaction.hide(name, terms))

    out = []
    for e in graph.elements:
        if e.kind not in STEPS or e.review_status == "rejected":
            continue
        claims = [records[c] for c in claims_of.get(e.id, []) if c in records]
        out.append(BoundaryStep(
            element_id=e.id, label=e.label, lane_role=lanes.get(e.lane_role_id or "", ""),
            claims=[BoundaryClaim(
                question_id=asked.get(c.segment_ids[0], "") if c.segment_ids else "",
                responsible=role_of(str(c.payload.get("responsible_role", ""))),
                text=redaction.hide(f"{c.payload.get('text', '')} {c.quote}".strip(), terms),
            ) for c in claims],
        ))  # fmt: skip
    return out


def lane_boundaries(sessions: Sessions, version_id: str) -> Result[list[LaneBoundaryFinding]]:
    with session_scope(sessions) as session:
        steps = steps_for(session, version_id)
    if steps is None:
        return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
    return Ok(boundaries.lane_boundaries(steps))
