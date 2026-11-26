"""Eric's record of who decides on paper, each step's system of record and how data moves at a
handoff (PRD §3.20; DECISIONS 110). Draft versions only; never filled by AI; each change audited.
None of these is an edit of the step: its review status stays as it is, and a refresh keeps them.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import DataMove, ElementKind, PaperDecider, SourceKind, SystemOfRecord
from app.domain.graph import ElementDetail, GraphEdge
from app.domain.models import (
    DataMoveInput,
    PaperDeciderInput,
    SystemOfRecordInput,
    VersionView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo
from app.services import accountability, grounding

Sessions = sessionmaker[Session]

ELEMENT_MISSING = versions_action.ELEMENT_MISSING
EDGE_MISSING = "That line doesn't exist."
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
NOT_DECIDING = "Only a decision or approval has a decider."
NOT_A_STEP = "Only a step (an activity, decision or approval) has a system of record."
NOT_A_HANDOFF = "Only a handoff (a line between steps in two lanes) says how the data moves."
BAD_PAPER = "Choose a role the documents name, or that no document names one."
BAD_ROLE = "Choose one of this engagement's roles."
BAD_PASSAGE = "Choose one of the document passages this step cites."
BAD_SYSTEM = "Choose a system, another system, or none (paper or memory)."
NOT_A_SYSTEM = "Choose a role marked as a system, or another system by name."
BAD_OTHER = "Name the system in 1 to 80 characters."
PERSON = "Name the role, not the person."
CHECK_LIMIT = 200
BAD_CHECK = "Say what checks it in one line of up to 200 characters."
BAD_MOVE = "Choose how the data moves, or that it isn't known."
STEPS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _draft(session: Session, version_id: str | None) -> Result[VersionView]:
    version = versions_repo.get(session, version_id) if version_id else None
    if version is None:
        return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
    if version.state != "draft":
        return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
    return Ok(version)


def set_paper_decider(config: AppConfig, sessions: Sessions, element_id: str,
                      body: PaperDeciderInput) -> Result[ElementDetail]:  # fmt: skip
    """The decider the documents name: a role, or that none names one, with the passage."""
    with session_scope(sessions) as session:
        match _draft(session, map_repo.element_version_id(session, element_id)):
            case Err() as err:
                return err
            case Ok(value=version):
                pass
        record = map_repo.element(session, element_id)
        if record is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if record.kind not in accountability.DECIDING:
            return _invalid("element_id", NOT_DECIDING)
        fields: dict[str, object]
        if body.status is None:
            fields = {"paper_decider_status": None, "paper_decider_role_id": None,
                      "paper_decider_segment_id": None}  # fmt: skip
        elif body.status == PaperDecider.NOT_NAMED.value:
            fields = {"paper_decider_status": body.status, "paper_decider_role_id": None,
                      "paper_decider_segment_id": None}  # fmt: skip
        elif body.status == PaperDecider.NAMED.value:
            roles = {r.id for r in engagements_repo.list_roles(session, version.engagement_id)}
            if body.role_id not in roles:
                return _invalid("role_id", BAD_ROLE)
            cited = {
                p.evidence.segment_id
                for p in map_repo.evidence(session, version.id)
                if p.evidence.element_id == element_id
                and p.evidence.verified
                and p.evidence.source_kind != SourceKind.INTERVIEW_TRANSCRIPT.value
            }
            if body.segment_id is not None and body.segment_id not in cited:
                return _invalid("segment_id", BAD_PASSAGE)
            fields = {"paper_decider_status": body.status, "paper_decider_role_id": body.role_id,
                      "paper_decider_segment_id": body.segment_id}  # fmt: skip
        else:
            return _invalid("status", BAD_PAPER)
        before = {k: getattr(record, k) for k in fields}
        if before != fields:
            map_repo.update_element(session, element_id, fields)
            audit.record(session, actor=actor_name(config), action="Recorded decider on paper",
                         target_type="element", target_id=element_id,
                         engagement_id=version.engagement_id, version_id=version.id,
                         before=before, after=fields)  # fmt: skip
    return versions_action.get_element(sessions, element_id)


def set_system_of_record(config: AppConfig, sessions: Sessions, element_id: str,
                         body: SystemOfRecordInput) -> Result[ElementDetail]:  # fmt: skip
    """The system the step's data is kept in: a role marked as a system, another system by
    name, or none (paper or memory)."""
    other = " ".join(body.other.split())
    with session_scope(sessions) as session:
        match _draft(session, map_repo.element_version_id(session, element_id)):
            case Err() as err:
                return err
            case Ok(value=version):
                pass
        record = map_repo.element(session, element_id)
        if record is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if record.kind not in STEPS:
            return _invalid("element_id", NOT_A_STEP)
        fields: dict[str, object] = {"system_status": body.status, "system_role_id": None,
                                     "system_other": None}  # fmt: skip
        if body.status == SystemOfRecord.SYSTEM.value:
            systems = {r.id for r in engagements_repo.list_roles(session, version.engagement_id)
                       if r.is_system}  # fmt: skip
            if body.role_id not in systems:
                return _invalid("role_id", NOT_A_SYSTEM)
            fields["system_role_id"] = body.role_id
        elif body.status == SystemOfRecord.OTHER.value:
            if not 1 <= len(other) <= accountability.MAX_ROLE:
                return _invalid("other", BAD_OTHER)
            terms = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
            if grounding.scan_redaction_terms(other, terms):
                return _invalid("other", PERSON)
            fields["system_other"] = other
        elif body.status not in (None, SystemOfRecord.NONE.value):
            return _invalid("status", BAD_SYSTEM)
        before = {k: getattr(record, k) for k in fields}
        if before != fields:
            map_repo.update_element(session, element_id, fields)
            audit.record(session, actor=actor_name(config), action="Recorded system of record",
                         target_type="element", target_id=element_id,
                         engagement_id=version.engagement_id, version_id=version.id,
                         before=before, after=fields)  # fmt: skip
    return versions_action.get_element(sessions, element_id)


def set_data_move(config: AppConfig, sessions: Sessions, version_id: str, edge_id: str,
                  body: DataMoveInput) -> Result[GraphEdge]:  # fmt: skip
    """How the data moves at a handoff, and what checks it (DECISIONS 113); never set without
    Eric. A field left out of the body is left as it is."""
    sent = body.model_fields_set
    if body.data_move is not None and body.data_move not in {m.value for m in DataMove}:
        return _invalid("data_move", BAD_MOVE)
    check = " ".join((body.check or "").split())
    if "check" in sent and len(check) > CHECK_LIMIT:
        return _invalid("check", BAD_CHECK)
    with session_scope(sessions) as session:
        found = map_repo.edge(session, edge_id)
        if found is None or found[0] != version_id:
            return Err(ErrorKind.NOT_FOUND, EDGE_MISSING)
        match _draft(session, version_id):
            case Err() as err:
                return err
            case Ok(value=version):
                pass
        _, edge = found
        ends = {e.id: e for e in map_repo.elements(session, version_id)}
        start, end = ends.get(edge.from_element_id), ends.get(edge.to_element_id)
        if (
            start is None or end is None or start.kind not in STEPS or end.kind not in STEPS
            or start.lane_role_id == end.lane_role_id
        ):  # fmt: skip
            return _invalid("edge_id", NOT_A_HANDOFF)
        terms = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
        if check and grounding.scan_redaction_terms(check, terms):
            return _invalid("check", PERSON)
        changes: dict[str, object] = {}
        if "data_move" in sent and edge.data_move != body.data_move:
            changes["data_move"] = body.data_move
        if "check" in sent and edge.data_check != check:
            changes["data_check"] = check
        if changes:
            updated = map_repo.update_edge(session, edge_id, changes)
            assert updated is not None
            edge = updated
            audit.record(session, actor=actor_name(config), action="Recorded how data moves",
                         target_type="edge", target_id=edge_id,
                         engagement_id=version.engagement_id, version_id=version.id,
                         before={k: getattr(found[1], k) for k in changes},
                         after=changes)  # fmt: skip
        return Ok(GraphEdge(id=edge.id, from_=edge.from_element_id, to=edge.to_element_id,
                            kind=edge.kind, label=edge.label,
                            sequence_basis=edge.sequence_basis,
                            view_membership=edge.view_membership,
                            information_payload=edge.information_payload,
                            typical=edge.typical, provenance=edge.provenance,
                            data_move=edge.data_move, data_check=edge.data_check))  # fmt: skip
