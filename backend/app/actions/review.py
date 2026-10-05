"""Reviewing a draft's steps (PRD §3.5 versions and locking, §5.7.5, §5.8; phase P6).

Confirm, reject and restore change a step's review status. Confirmed, edited and added steps are
locked: no pipeline run ever writes to them (constraint 8). Only a draft version changes; start
and end come from the scope card. Every change writes an audit row and refreshes the version's
stored lint report, so the quality card and the Lint tab never show a stale state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import (
    AiBasis,
    AiComponent,
    CauseType,
    ConstraintType,
    DecisionMechanism,
    ElementKind,
    Provenance,
    RaciLetter,
    ReviewStatus,
    WorkType,
)
from app.domain.graph import AiFlagRecord, ConstraintRecord, ElementDetail, RaciRecord
from app.domain.models import (
    AiFlagInput,
    AuditEntry,
    ConstraintInput,
    DecisionInput,
    ElementPatch,
    HandoffInput,
    RaciInput,
    WorkTypeInput,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo
from app.services import grounding, sensemaking

Sessions = sessionmaker[Session]

LOCKED = {ReviewStatus.CONFIRMED.value, ReviewStatus.EDITED.value, ReviewStatus.ADDED.value}
STRUCTURAL = {ElementKind.START.value, ElementKind.END.value}
DRAFT_STATE = "draft"

ELEMENT_MISSING = versions_action.ELEMENT_MISSING
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
STRUCTURAL_STEP = (
    "Start and end come from the engagement's trigger and end point; change them on Setup."
)
RESTORE_FIRST = "This step is rejected. Restore it before confirming it."
NOT_REJECTED = "Only a rejected step can be restored."

ACTIONS = {
    "confirm": "Confirmed step",
    "reject": "Rejected step",
    "restore": "Restored step",
}


def _next_status(action: str, current: str) -> Result[str]:
    if action == "confirm":
        if current == ReviewStatus.REJECTED.value:
            return Err(ErrorKind.CONFLICT, RESTORE_FIRST)
        return Ok(current if current in LOCKED else ReviewStatus.CONFIRMED.value)
    if action == "reject":
        return Ok(ReviewStatus.REJECTED.value)
    if current != ReviewStatus.REJECTED.value:
        return Err(ErrorKind.CONFLICT, NOT_REJECTED)
    return Ok(ReviewStatus.DRAFT.value)


def review(
    config: AppConfig, sessions: Sessions, element_id: str, action: str
) -> Result[ElementDetail]:
    """Confirm, reject or restore one step (`action` is a key of ACTIONS)."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        element = map_repo.element(session, element_id)
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        if element is None or version is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if element.kind in STRUCTURAL:
            return Err(ErrorKind.VALIDATION, STRUCTURAL_STEP, {"field": "kind"})
        match _next_status(action, element.review_status):
            case Err() as err:
                return err
            case Ok(value=status):
                pass
        if status != element.review_status:
            map_repo.update_element(session, element_id, {"review_status": status})
            audit.record(
                session,
                actor=actor,
                action=ACTIONS[action],
                target_type="element",
                target_id=element_id,
                engagement_id=version.engagement_id,
                version_id=version.id,
                before={"review_status": element.review_status},
                after={"review_status": status},
            )
    if status != element.review_status:
        versions_action.lint_version(sessions, version.id)
    return versions_action.get_element(sessions, element_id)


def get_audit(sessions: Sessions, version_id: str) -> Result[list[AuditEntry]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        terms = redaction.name_replacements(session, version.engagement_id)
        labels = {e.id: e.label for e in map_repo.elements(session, version_id)}
        rows = audit.list_for_version(session, version_id)
    return Ok(
        [
            AuditEntry(
                **row,
                target_label=redaction.hide(labels.get(row["target_id"], ""), terms),
            )
            for row in rows
        ]
    )


# --- Editing a step (PRD §5.7.6 field rules; shared by the edit form, table view and Add step) ---

STEP_KINDS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
CLASSIFIED = {DecisionMechanism.RULE_BASED.value, DecisionMechanism.JUDGMENT.value}
JUDGMENT = DecisionMechanism.JUDGMENT.value
MAX_MINUTES = 10_000
TEXT_LIMITS = {
    "duration_text": 200,
    "kpi": 300,
    "handoff.in": 300,
    "handoff.out": 300,
    "decision.rule_or_threshold": 500,
    "decision.escalation": 500,
    "k_risk": 500,
}
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."
EDIT_REJECTED = "This step is rejected. Restore it before editing it."


@dataclass
class StepFields:
    """Everything the field rules look at: a step as it would be after the change."""

    label: str
    kind: str
    lane_role_id: str | None
    work_min: float | None = None
    wait_min: float | None = None
    duration_text: str = ""
    complexity: str | None = None
    kpi: str = ""
    decision: DecisionInput = field(default_factory=lambda: DecisionInput(mechanism="none"))
    handoff: HandoffInput = field(default_factory=HandoffInput)
    constraints: list[ConstraintInput] = field(default_factory=list)
    k_risk: str = ""
    ai_flag: AiFlagInput | None = None
    raci: list[RaciInput] = field(default_factory=list)


def _invalid(where: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": where})


def _texts(step: StepFields) -> list[tuple[str, str, str]]:
    """(field, words for messages, text) for every free text of a step."""
    texts = [
        ("label", "The name", step.label),
        ("duration_text", "The time window", step.duration_text),
        ("kpi", "The KPI", step.kpi),
        ("handoff.in", "Handoff in", step.handoff.in_),
        ("handoff.out", "Handoff out", step.handoff.out),
        ("decision.rule_or_threshold", "The rule or threshold", step.decision.rule_or_threshold),
        ("decision.escalation", "The escalation", step.decision.escalation),
        ("k_risk", "The knowledge risk", step.k_risk),
    ]
    texts += [("constraints", "A constraint", c.text) for c in step.constraints]
    if step.ai_flag:
        flag = step.ai_flag
        texts += [("ai_flag.input", "The AI flag", flag.input),
                  ("ai_flag.output", "The AI flag", flag.output),
                  ("ai_flag.handoff", "The AI flag", flag.handoff)]  # fmt: skip
    return texts


def check_raci(kind: str, raci: list[RaciInput], roles: set[str]) -> Result[None]:
    letters = {x.value for x in RaciLetter}
    seen: set[tuple[str, str]] = set()
    for entry in raci:
        if entry.role_id not in roles:
            return _invalid("raci", "Choose one of this engagement's roles for each RACI letter.")
        if entry.letter not in letters:
            return _invalid("raci", "RACI letters are R, A, C or I.")
        if (entry.role_id, entry.letter) in seen:
            return _invalid("raci", "Each role can have each letter only once.")
        seen.add((entry.role_id, entry.letter))
    accountable = [e for e in raci if e.letter == RaciLetter.ACCOUNTABLE.value]
    if not accountable:
        return _invalid("raci", "Choose who is Accountable for this step.")
    if len(accountable) > 1 and not all(e.contested for e in accountable):
        return _invalid(
            "raci",
            "A step has one Accountable role. Keep one, or mark them all as contested when the "
            "sources disagree.",
        )
    responsible = [e for e in raci if e.letter == RaciLetter.RESPONSIBLE.value]
    if kind == ElementKind.ACTIVITY.value and len(responsible) != 1:
        return _invalid("raci", "An activity needs exactly one Responsible role.")
    return Ok(None)


def check_step(
    step: StepFields,
    roles: set[str],
    hidden: list[str],
    *,
    raci: bool = True,
    work_type: str | None = None,
) -> Result[None]:
    """The field rules of PRD §5.7.6; the first problem found, naming its field. `work_type` is
    the step's stored work type (complex and chaotic steps are never automation candidates)."""
    label = step.label.strip()
    if not label or len(label) > 120 or "\n" in label:
        return _invalid("label", "Please give the step a name of up to 120 characters.")
    if step.kind not in STEP_KINDS:
        return _invalid("kind", "A step is an activity, a decision or an approval.")
    if step.lane_role_id not in roles:
        return _invalid("lane_role_id", "Choose the lane (role) this step sits in.")
    for name, minutes in (("work_min", step.work_min), ("wait_min", step.wait_min)):
        if minutes is not None and not 0 <= minutes <= MAX_MINUTES:
            return _invalid(name, "Minutes must be between 0 and 10,000.")
    if step.complexity not in (None, "L", "M", "H"):
        return _invalid("complexity", "Complexity is L, M or H.")
    for where, words, text in _texts(step):
        limit = TEXT_LIMITS.get(where, 300)
        if where != "label" and len(text) > limit:
            return _invalid(where, f"{words} can be up to {limit:,} characters.")
        if grounding.scan_redaction_terms(text, hidden):  # the name itself is never echoed
            return _invalid(where, HIDDEN_NAME.format(what=words))
    mechanism = step.decision.mechanism
    if mechanism not in {m.value for m in DecisionMechanism}:
        return _invalid("decision.mechanism", "The mechanism is rule-based or judgment.")
    if step.kind in DECIDING and mechanism not in CLASSIFIED:
        return _invalid(
            "decision.mechanism",
            "Say whether this decision or approval follows a rule or is a judgment call.",
        )
    if step.decision.decider_role_id not in (None, *roles):
        return _invalid("decision.decider_role_id", "Choose the decider from the roles.")
    causes = {c.value for c in CauseType}
    provenances = {p.value for p in Provenance}
    for c in step.constraints:
        if not c.text.strip():
            return _invalid("constraints", "A constraint needs some text.")
        if c.cause_type not in (None, *causes):
            return _invalid("constraints", "Choose a cause type from the list.")
        if c.provenance not in provenances:
            return _invalid("constraints", "A constraint's provenance is O, I or R.")
    if step.ai_flag is not None:
        flag = step.ai_flag
        if flag.component not in {c.value for c in AiComponent}:
            return _invalid("ai_flag.component", "Choose the AI component from the list.")
        for where, text in (("ai_flag.input", flag.input), ("ai_flag.output", flag.output),
                            ("ai_flag.handoff", flag.handoff)):  # fmt: skip
            if not text.strip():
                return _invalid(where, "An AI flag needs its input, output and handoff.")
        if flag.basis not in {b.value for b in AiBasis}:
            return _invalid("ai_flag.basis", "Choose the basis from the list.")
        automate = flag.basis == AiBasis.RULE_BASED_AUTOMATE_CANDIDATE.value
        if automate and mechanism == DecisionMechanism.JUDGMENT.value:
            return _invalid(
                "ai_flag.basis",
                "A judgment step is never an automation candidate. Choose support only.",
            )
        if automate and work_type in sensemaking.NEVER_AUTOMATED:
            return _invalid(
                "ai_flag.basis",
                f"This step is {work_type} work, so it is never an automation candidate. "
                "Choose support only.",
            )
    return check_raci(step.kind, step.raci, roles) if raci else Ok(None)


def _current(session: Session, version_id: str, element_id: str) -> StepFields | None:
    e = map_repo.element(session, element_id)
    if e is None:
        return None
    flag = next((f for f in map_repo.ai_flags(session, version_id) if f.element_id == e.id), None)
    return StepFields(
        label=e.label, kind=e.kind, lane_role_id=e.lane_role_id, work_min=e.work_min,
        wait_min=e.wait_min, duration_text=e.duration_text, complexity=e.complexity, kpi=e.kpi,
        decision=DecisionInput(mechanism=e.decision_mechanism, decider_role_id=e.decider_role_id,
                               rule_or_threshold=e.rule_or_threshold, escalation=e.escalation),
        handoff=HandoffInput(in_=e.handoff_in, out=e.handoff_out),
        constraints=[ConstraintInput(text=c.text, cause_type=c.cause_type, is_key=c.is_key,
                                     provenance=c.provenance)
                     for c in map_repo.constraints(session, version_id) if c.element_id == e.id],
        k_risk=e.k_risk,
        ai_flag=AiFlagInput(component=flag.component, input=flag.input, output=flag.output,
                            handoff=flag.handoff, basis=flag.basis) if flag else None,
        raci=[RaciInput(role_id=r.role_id, letter=r.letter, contested=r.contested)
              for r in map_repo.raci(session, version_id) if r.element_id == e.id],
    )  # fmt: skip


EMPTY: dict[str, object] = {
    "label": "",
    "kind": "",
    "duration_text": "",
    "kpi": "",
    "k_risk": "",
    "constraints": [],
    "raci": [],
}


def _patched(before: StepFields, patch: ElementPatch) -> StepFields:
    """The step with the sent fields applied; a `null` text or list counts as empty."""
    after = replace(before)
    for name in patch.model_fields_set:
        value = getattr(patch, name)
        if value is None and name in EMPTY:
            value = EMPTY[name]
        elif value is None and name == "decision":
            value = DecisionInput(mechanism=DecisionMechanism.NONE.value)
        elif value is None and name == "handoff":
            value = HandoffInput()
        setattr(after, name, value)
    return after


def _plain(step: StepFields) -> dict[str, object]:
    """A step's fields as JSON for audit rows."""
    data = asdict(step)
    data["decision"] = step.decision.model_dump()
    data["handoff"] = {"in": step.handoff.in_, "out": step.handoff.out}
    data["constraints"] = [c.model_dump() for c in step.constraints]
    data["ai_flag"] = step.ai_flag.model_dump() if step.ai_flag else None
    data["raci"] = [r.model_dump() for r in step.raci]
    return data


def edit(
    config: AppConfig, sessions: Sessions, element_id: str, patch: ElementPatch
) -> Result[ElementDetail]:
    """Change a step's fields and/or RACI (only those sent); it becomes `edited` and locked."""
    actor = actor_name(config)
    sent = patch.model_fields_set
    with session_scope(sessions) as session:
        element = map_repo.element(session, element_id)
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        if element is None or version is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if element.kind in STRUCTURAL:
            return Err(ErrorKind.VALIDATION, STRUCTURAL_STEP, {"field": "kind"})
        if element.review_status == ReviewStatus.REJECTED.value:
            return Err(ErrorKind.CONFLICT, EDIT_REJECTED)
        before = _current(session, version.id, element_id)
        assert before is not None
        after = _patched(before, patch)
        roles = {r.id for r in engagements_repo.list_roles(session, version.engagement_id)}
        hidden = [t.term for t in redaction.name_replacements(session, version.engagement_id)]
        check = check_step(
            after, roles, hidden, raci="raci" in sent or "kind" in sent, work_type=element.work_type
        )
        if isinstance(check, Err):
            return check
        old, new = _plain(before), _plain(after)
        changed = sorted(k for k in new if new[k] != old[k])
        if not changed:
            return versions_action.get_element(sessions, element_id)
        status = element.review_status
        if status != ReviewStatus.ADDED.value:
            status = ReviewStatus.EDITED.value
        _write(session, element_id, after, changed, status)
        audit.record(
            session,
            actor=actor,
            action="Edited step",
            target_type="element",
            target_id=element_id,
            engagement_id=version.engagement_id,
            version_id=version.id,
            before={k: old[k] for k in changed} | {"review_status": element.review_status},
            after={k: new[k] for k in changed} | {"review_status": status},
        )
    versions_action.lint_version(sessions, version.id)
    return versions_action.get_element(sessions, element_id)


def set_raci(
    config: AppConfig, sessions: Sessions, element_id: str, raci: list[RaciInput]
) -> Result[ElementDetail]:
    return edit(config, sessions, element_id, ElementPatch(raci=raci))


def _write(
    session: Session,
    element_id: str,
    step: StepFields,
    changed: list[str],
    status: str,
) -> None:
    map_repo.update_element(
        session,
        element_id,
        {
            "label": step.label.strip(),
            "kind": step.kind,
            "lane_role_id": step.lane_role_id,
            "work_min": step.work_min,
            "wait_min": step.wait_min,
            "duration_text": step.duration_text,
            "complexity": step.complexity,
            "kpi": step.kpi,
            "decision_mechanism": step.decision.mechanism,
            "decider_role_id": step.decision.decider_role_id,
            "rule_or_threshold": step.decision.rule_or_threshold,
            "escalation": step.decision.escalation,
            "handoff_in": step.handoff.in_,
            "handoff_out": step.handoff.out,
            "k_risk": step.k_risk,
            "review_status": status,
        },
    )
    if "constraints" in changed:
        map_repo.replace_constraints(
            session,
            element_id,
            [ConstraintRecord(element_id=element_id, text=c.text.strip(), provenance=c.provenance,
                              cause_type=c.cause_type, is_key=c.is_key)
             for c in step.constraints],
        )  # fmt: skip
    if "ai_flag" in changed:
        flag = step.ai_flag
        map_repo.replace_ai_flag(
            session,
            element_id,
            AiFlagRecord(element_id=element_id, component=flag.component, input=flag.input,
                         output=flag.output, handoff=flag.handoff, basis=flag.basis)
            if flag else None,
        )  # fmt: skip
    if "raci" in changed:
        map_repo.replace_raci(
            session,
            element_id,
            [RaciRecord(element_id=element_id, role_id=r.role_id, letter=r.letter,
                        contested=r.contested) for r in step.raci],
        )  # fmt: skip


# --- Work type: confirm or change (PRD §3.12.4, §5.7.7 4a, criterion 54; 2026-10-05, V3b) -------

CHOOSABLE_WORK_TYPES = [w.value for w in WorkType if w is not WorkType.NOT_CLASSIFIED]
CONSTRAINT_TYPES = {c.value for c in ConstraintType}
WORK_TYPE_QUESTION = "work_type"


def set_work_type(
    config: AppConfig, sessions: Sessions, element_id: str, body: WorkTypeInput
) -> Result[ElementDetail]:
    """Eric confirms the proposed work type or changes it (API_CONTRACT.md → Review)."""
    if not body.confirm:
        return _invalid("confirm", "Confirm the work type to save it.")
    if body.work_type not in CHOOSABLE_WORK_TYPES:
        return _invalid("work_type", "Choose the kind of work this step is.")
    constraint = (
        body.constraint_type
        if "constraint_type" in body.model_fields_set
        else sensemaking.CONSTRAINT_FOR.get(body.work_type)
    )
    if constraint is not None and constraint not in CONSTRAINT_TYPES:
        return _invalid("constraint_type", "Choose the constraint type from the list.")
    actor = actor_name(config)
    with session_scope(sessions) as session:
        element = map_repo.element(session, element_id)
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        if element is None or version is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if element.kind in STRUCTURAL:
            return Err(ErrorKind.VALIDATION, STRUCTURAL_STEP, {"field": "kind"})
        if element.review_status == ReviewStatus.REJECTED.value:
            return Err(ErrorKind.CONFLICT, EDIT_REJECTED)
        before: dict[str, object] = {
            "work_type": element.work_type,
            "constraint_type": element.constraint_type,
            "work_type_status": element.work_type_status,
        }
        after: dict[str, object] = {
            "work_type": body.work_type,
            "constraint_type": constraint,
            "work_type_status": sensemaking.CONFIRMED,
        }
        changed = (element.work_type, element.constraint_type) != (body.work_type, constraint)
        status = element.review_status
        if changed and status != ReviewStatus.ADDED.value:
            status = ReviewStatus.EDITED.value
        updates = dict(after)
        if status != element.review_status:
            before["review_status"], after["review_status"] = element.review_status, status
            updates["review_status"] = status
        # Complex or chaotic work is never an automation candidate, and is a judgment step
        # (constraint 7, criterion 55).
        if body.work_type in sensemaking.NEVER_AUTOMATED:
            flag = next(
                (f for f in map_repo.ai_flags(session, version.id) if f.element_id == element_id),
                None,
            )
            if flag is not None and flag.basis == AiBasis.RULE_BASED_AUTOMATE_CANDIDATE.value:
                map_repo.replace_ai_flag(session, element_id, None)
                before["ai_flag"], after["ai_flag"] = flag.basis, None
            if element.kind in DECIDING and element.decision_mechanism != JUDGMENT:
                updates["decision_mechanism"] = JUDGMENT
                before["decision_mechanism"] = element.decision_mechanism
                after["decision_mechanism"] = JUDGMENT
        if before == after:
            return versions_action.get_element(sessions, element_id)
        map_repo.update_element(session, element_id, updates)
        for q in map_repo.questions(session, version.id):
            if q.element_id == element_id and q.reason == WORK_TYPE_QUESTION and q.status == "open":
                map_repo.set_question_status(session, q.id, "answered")
        audit.record(
            session,
            actor=actor,
            action="Changed work type" if changed else "Confirmed work type",
            target_type="element",
            target_id=element_id,
            engagement_id=version.engagement_id,
            version_id=version.id,
            before=before,
            after=after,
        )
    versions_action.lint_version(sessions, version.id)
    return versions_action.get_element(sessions, element_id)
