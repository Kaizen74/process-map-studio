"""Eric's own changes to a draft's structure (PRD §4 Review, §5.7.6 Add missing step; phase P6):
adding a step he knows is missing, and adding, changing or removing the lines between steps.

An added step is never an AI claim (constraint 2): an observed (`O`) step carries the passages
Eric picked, a recommended (`R`) step his typed reference. It is `added` and so locked against
pipeline runs. Every change is audited and re-lints the version.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.review import (
    DRAFT_STATE,
    NOT_A_DRAFT,
    StepFields,
    check_step,
)
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import (
    DecisionMechanism,
    EdgeKind,
    ElementKind,
    Provenance,
    RaciLetter,
    ReviewStatus,
    Stance,
)
from app.domain.graph import (
    EdgeRecord,
    ElementDetail,
    ElementRecord,
    EvidenceRecord,
    GraphEdge,
    RaciRecord,
)
from app.domain.models import (
    DecisionInput,
    EdgeInput,
    EdgePatch,
    NewStep,
    RaciInput,
    VersionView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.s2_canonicalise import stable_key
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import grounding

Sessions = sessionmaker[Session]

VERSION_MISSING = versions_action.VERSION_MISSING
EDGE_MISSING = "That line doesn't exist."
OFF_MAIN_PATH = versions_action.OFF_MAIN_PATH
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
CLASSIFIED = {DecisionMechanism.RULE_BASED.value, DecisionMechanism.JUDGMENT.value}
NEEDS_PASSAGE = "Pick the passage this step comes from."
NEEDS_REFERENCE = "Type the reference this recommended step comes from."
O_OR_R = "Choose Observed (with a passage) or Recommended (with a reference)."
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."


def _invalid(where: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": where})


def _draft(session: Session, version_id: str) -> Result[VersionView]:
    version = versions_repo.get(session, version_id)
    if version is None:
        return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
    if version.state != DRAFT_STATE:
        return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
    return Ok(version)


def add_step(
    config: AppConfig, sessions: Sessions, version_id: str, new: NewStep
) -> Result[ElementDetail]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        match _draft(session, version_id):
            case Err() as err:
                return err
            case Ok(value=version):
                pass
        elements = {e.id: e for e in map_repo.elements(session, version_id)}
        after = elements.get(new.after_element_id)
        if after is None or after.kind == ElementKind.END.value:
            return _invalid("after_element_id", "Choose the step the new one comes after.")
        roles = {r.id for r in engagements_repo.list_roles(session, version.engagement_id)}
        hidden = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
        deciding = new.kind in DECIDING
        if deciding and new.mechanism not in CLASSIFIED:
            return _invalid("mechanism", "Say whether it follows a rule or is a judgment call.")
        lane = new.lane_role_id
        raci = [RaciInput(role_id=lane, letter=RaciLetter.ACCOUNTABLE.value)]
        if new.kind == ElementKind.ACTIVITY.value:
            raci.insert(0, RaciInput(role_id=lane, letter=RaciLetter.RESPONSIBLE.value))
        step = StepFields(
            label=new.label,
            kind=new.kind,
            lane_role_id=lane,
            decision=DecisionInput(
                mechanism=new.mechanism if deciding else DecisionMechanism.NONE.value,
                decider_role_id=lane if deciding else None,
            ),
            raci=raci,
        )
        if isinstance(check := check_step(step, roles, hidden), Err):
            return check
        links: list[EvidenceRecord] = []
        match new.provenance:
            case Provenance.OBSERVED.value:
                owners = sources_repo.segment_owners(session, new.segment_ids)
                if not new.segment_ids:
                    return _invalid("segment_ids", NEEDS_PASSAGE)
                for sid in new.segment_ids:
                    owner = owners.get(sid)
                    if owner is None or owner[1] != version.engagement_id:
                        return _invalid(
                            "segment_ids", "Pick a passage from this engagement's sources."
                        )
                    links.append(
                        EvidenceRecord(segment_id=sid, source_kind=owner[2],
                                       stance=Stance.SUPPORTS.value, verified=True)
                    )  # fmt: skip
            case Provenance.RECOMMENDED.value:
                reference = new.r_reference.strip()
                if not 1 <= len(reference) <= 500:
                    return _invalid("r_reference", NEEDS_REFERENCE)
                if grounding.scan_redaction_terms(reference, hidden):
                    return _invalid("r_reference", HIDDEN_NAME.format(what="The reference"))
            case _:
                return _invalid("provenance", O_OR_R)

        [added] = map_repo.add_elements(
            session,
            version_id,
            [
                ElementRecord(
                    stable_key=stable_key(new.label, map_repo.stable_keys(session, version_id)),
                    kind=new.kind,
                    label=new.label.strip(),
                    lane_role_id=lane,
                    phase_id=after.phase_id,
                    decision_mechanism=step.decision.mechanism,
                    decider_role_id=step.decision.decider_role_id,
                    provenance=new.provenance,
                    r_reference=new.r_reference.strip() if new.provenance == "R" else "",
                    review_status=ReviewStatus.ADDED.value,
                )
            ],
        )
        map_repo.add_raci(
            session,
            [RaciRecord(element_id=added.id, role_id=r.role_id, letter=r.letter) for r in raci],
        )
        map_repo.add_evidence(session, [ln.model_copy(update={"element_id": added.id})
                                         for ln in links])  # fmt: skip
        insert_after(session, version_id, after.id, added.id)
        audit.record(
            session,
            actor=actor,
            action="Added step",
            target_type="element",
            target_id=added.id,
            engagement_id=version.engagement_id,
            version_id=version_id,
            after={"kind": new.kind, "label": added.label, "provenance": new.provenance,
                   "after_element_id": after.id, "passages": len(links)},
        )  # fmt: skip
    versions_action.lint_version(sessions, version_id)
    return versions_action.get_element(sessions, added.id)


def insert_after(session: Session, version_id: str, after_id: str, new_id: str) -> None:
    """Put a new step into the flow after another: it takes over the first main-path line out
    of that step, and a sequence line continues to where that line went (else it just follows)."""
    out = next(
        (e for e in map_repo.edges(session, version_id)
         if e.from_element_id == after_id and e.kind not in OFF_MAIN_PATH),
        None,
    )  # fmt: skip
    if out is None:
        line = EdgeRecord(
            from_element_id=after_id, to_element_id=new_id, kind=EdgeKind.SEQUENCE.value
        )
        map_repo.add_edges(session, version_id, [line])
        return
    map_repo.update_edge(session, out.id, {"to_element_id": new_id})
    line = EdgeRecord(
        from_element_id=new_id, to_element_id=out.to_element_id, kind=EdgeKind.SEQUENCE.value
    )
    map_repo.add_edges(session, version_id, [line])


# --- Lines between steps ---------------------------------------------------------------------


def _check_edge(
    edge: EdgeRecord,
    elements: dict[str, ElementRecord],
    others: list[EdgeRecord],
    hidden: list[str],
) -> Result[None]:
    source, target = elements.get(edge.from_element_id), elements.get(edge.to_element_id)
    if source is None or target is None:
        return _invalid("from", "Both ends of a line must be steps of this map.")
    if source.id == target.id:
        return _invalid("to", "A line can't go from a step to itself.")
    if source.kind == ElementKind.END.value or target.kind == ElementKind.START.value:
        return _invalid("to", "Lines can't leave the end or go into the start.")
    # "Not described" connectors are drawn by the translation only, where practice is silent.
    if edge.kind not in {k.value for k in EdgeKind} - {EdgeKind.GAP.value}:
        return _invalid("kind", "Choose the kind of line from the list.")
    label = edge.label.strip()
    if len(label) > 60:
        return _invalid("label", "A line's label can be up to 60 characters.")
    if source.kind in DECIDING and not label:
        return _invalid("label", "Every exit of a decision or approval needs a label.")
    if grounding.scan_redaction_terms(label, hidden):
        return _invalid("label", HIDDEN_NAME.format(what="The label"))
    same = (edge.from_element_id, edge.to_element_id, edge.kind)
    if any((o.from_element_id, o.to_element_id, o.kind) == same for o in others):
        return _invalid("to", "These two steps are already joined by a line of this kind.")
    return Ok(None)


def _view(edge: EdgeRecord) -> GraphEdge:
    return GraphEdge(id=edge.id, from_=edge.from_element_id, to=edge.to_element_id,
                     kind=edge.kind, label=edge.label, sequence_basis=edge.sequence_basis,
                     view_membership=edge.view_membership,
                     information_payload=edge.information_payload, typical=edge.typical,
                     provenance=edge.provenance)  # fmt: skip


def _plain(edge: EdgeRecord) -> dict[str, str]:
    return {"from": edge.from_element_id, "to": edge.to_element_id, "kind": edge.kind,
            "label": edge.label}  # fmt: skip


def _change_edge(
    config: AppConfig,
    sessions: Sessions,
    version_id: str,
    edge_id: str | None,
    change: EdgeInput | EdgePatch | None,
) -> Result[GraphEdge | None]:
    """Add (no edge_id), change (edge_id and change) or remove (edge_id, no change) a line."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        match _draft(session, version_id):
            case Err() as err:
                return err
            case Ok(value=version):
                pass
        current = None
        if edge_id is not None:
            found = map_repo.edge(session, edge_id)
            if found is None or found[0] != version_id:
                return Err(ErrorKind.NOT_FOUND, EDGE_MISSING)
            current = found[1]
        if change is None:
            assert current is not None
            map_repo.delete_edge(session, current.id)
            action, before, after, result = "Removed line", _plain(current), None, None
        else:
            base = current or EdgeRecord(from_element_id="", to_element_id="", kind="")
            sent = change.model_dump(exclude_unset=True)
            edge = base.model_copy(update={
                "from_element_id": sent.get("from_", base.from_element_id),
                "to_element_id": sent.get("to", base.to_element_id),
                "kind": sent.get("kind", base.kind),
                "label": (sent.get("label", base.label) or "").strip(),
            })  # fmt: skip
            elements = {e.id: e for e in map_repo.elements(session, version_id)}
            others = [e for e in map_repo.edges(session, version_id) if e.id != edge.id]
            hidden = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
            if isinstance(check := _check_edge(edge, elements, others, hidden), Err):
                return check
            if current is None:
                [result] = map_repo.add_edges(session, version_id, [edge])
                action, before, after = "Added line", None, _plain(result)
            else:
                # A line Eric edits is his: no longer one the translation re-works (provenance I).
                fields = {"from_element_id": edge.from_element_id,
                          "to_element_id": edge.to_element_id, "kind": edge.kind,
                          "label": edge.label, "provenance": Provenance.OBSERVED.value}  # fmt: skip
                updated = map_repo.update_edge(session, current.id, fields)
                assert updated is not None
                result = updated
                action, before, after = "Changed line", _plain(current), _plain(result)
        audit.record(
            session,
            actor=actor,
            action=action,
            target_type="edge",
            target_id=edge_id or (result.id if result else ""),
            engagement_id=version.engagement_id,
            version_id=version_id,
            before=before,
            after=after,
        )
    versions_action.lint_version(sessions, version_id)
    if result is None:
        return Ok(None)
    with session_scope(sessions) as session:  # as stored after the views were brought up to date
        stored = map_repo.edge(session, result.id)
    return Ok(_view(stored[1] if stored else result))


def add_edge(
    config: AppConfig, sessions: Sessions, version_id: str, edge: EdgeInput
) -> Result[GraphEdge | None]:
    return _change_edge(config, sessions, version_id, None, edge)


def change_edge(
    config: AppConfig, sessions: Sessions, version_id: str, edge_id: str, change: EdgePatch
) -> Result[GraphEdge | None]:
    return _change_edge(config, sessions, version_id, edge_id, change)


def remove_edge(
    config: AppConfig, sessions: Sessions, version_id: str, edge_id: str
) -> Result[GraphEdge | None]:
    return _change_edge(config, sessions, version_id, edge_id, None)
