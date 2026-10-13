"""Intent statements (API_CONTRACT.md → Intent; PRD §3.16, constraint 25, G16; phase P13a): what
the organisation intends, quoted from a policy or charter or stated by an owner. Eric adds
owner-stated statements and confirms, edits or dismisses every proposal; nothing proposed counts
until he confirms it. Names are hidden in every answer (G10); every change is audited."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, redaction
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import IntentKind, IntentMetric, IntentOrigin, VerificationStatus
from app.domain.models import NameReplacement
from app.domain.reality import IntentFields, IntentPatch, IntentRecord, IntentView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as elements_repo
from app.repositories import engagements as engagements_repo
from app.repositories import intent as repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import grounding

Sessions = sessionmaker[Session]

INTENT_MISSING = "That intent statement doesn't exist."
BAD_KIND = "Choose promise, target, control objective or policy rule."
BAD_SCOPE = "Choose process, phase or step."
BAD_STEP = "Choose a step of the current map."
BAD_PHASE = "Choose a phase of the current map."
BAD_TEXT = "Describe the intent in one line of up to 200 characters."
NAMED = "Use role names, not people's names."
BAD_METRIC = "Choose what the target measures."
NEED_TARGET = "Give the comparison, the target value and its unit."
TARGET_WITHOUT_METRIC = "A target value needs a metric."
BAD_OWNER = "Choose the owner's role."
BAD_DATE = "Give the date the target was set, for example 2026-10-01."
NOT_IN_QUOTE = "The target value must be in the quoted text."
OWNER_ON_DOCUMENT = "A statement quoted from a document has no owner or date to set."
BAD_STATUS = "Choose confirmed, dismissed or proposed."
BAD_NOTE = "A note is one line of up to 300 characters."
REJECTED = (
    "This statement failed the checks, so it can't be used. Add it yourself as an owner-stated "
    "target if it holds."
)
DOCUMENT_DELETE = "Dismiss a statement quoted from a document instead; it stays on record."
SCOPES = ("process", "phase", "step")
COMPARATORS = ("at_most", "at_least", "equals")
UNITS = ("min", "pct", "count")
STATUSES = ("confirmed", "dismissed", "proposed")
MAX_TEXT, MAX_NOTE = 200, 300
STATUS_ACTIONS = {"confirmed": "Confirmed intent statement",
                  "dismissed": "Dismissed intent statement",
                  "proposed": "Reopened intent statement"}  # fmt: skip
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _day(text: str) -> str:
    """2026-10-01 → "1 Oct 2026"."""
    d = date.fromisoformat(text)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _map_places(session: Session, engagement_id: str) -> tuple[dict[str, str], set[str]]:
    """The current map's steps (stable key → label) and phase names."""
    version_id = versions_repo.current_map_id(session, engagement_id)
    if version_id is None:
        return {}, set()
    steps = {
        e.stable_key: e.label
        for e in elements_repo.elements(session, version_id)
        if e.kind not in ("start", "end") and e.review_status != "rejected"
    }
    return steps, {p.name for p in elements_repo.phases(session, version_id)}


def _views(session: Session, engagement_id: str, rows: list[IntentRecord]) -> list[IntentView]:
    terms = redaction.name_replacements(session, engagement_id)
    steps, _ = _map_places(session, engagement_id)
    roles = {r.id: r.name for r in engagements_repo.list_roles(session, engagement_id)}
    anchors, _ = lenses.places(session, [r.segment_ids[0] for r in rows if r.segment_ids])
    names: dict[str, str] = {}
    for sid in {r.source_id for r in rows if r.source_id}:
        found = sources_repo.get(session, sid)
        names[sid] = found.filename if found else ""

    def hide(text: str) -> str:
        return redaction.hide(text, terms)

    out = []
    for r in rows:
        anchor = anchors.get(r.segment_ids[0], "") if r.segment_ids else ""
        owner = roles.get(r.owner_role_id or "", "")
        source = names.get(r.source_id or "", "")
        if r.origin == IntentOrigin.OWNER_STATED.value:
            label = f"Target set by {owner}" + (f", {_day(r.stated_on)}" if r.stated_on else "")
        else:
            label = f"Quoted from {source} {anchor}".strip()
        out.append(IntentView(
            id=r.id, engagement_id=r.engagement_id, scope=r.scope,
            element_stable_key=r.element_stable_key,
            element_label=steps.get(r.element_stable_key or "", ""), phase_name=r.phase_name,
            kind=r.kind, origin=r.origin, text=hide(r.text), metric=r.metric,
            comparator=r.comparator, target_value=r.target_value, unit=r.unit,
            source_id=r.source_id, source_name=hide(source), anchor=anchor, quote=hide(r.quote),
            owner_role_id=r.owner_role_id, owner_role_name=owner, stated_on=r.stated_on,
            label=hide(label), verification_status=r.verification_status,
            rejection_guardrail=r.rejection_guardrail, status=r.status, note=r.note,
            created_at=r.created_at,
        ))  # fmt: skip
    return out


def _unit_fits(metric: str, unit: str) -> bool:
    if metric.endswith("_min"):
        return unit == "min"
    if metric.endswith("_pct"):
        return unit == "pct"
    return True


def _in_quote(value: float, quote: str) -> bool:
    """G5 for a target value: the number (or the offset T-n) appears in the quoted text."""
    number = str(int(value)) if float(value).is_integer() else str(value)
    found = grounding.numbers_in(quote)
    return number in found or f"T-{number}" in found


def _check(
    session: Session,
    engagement_id: str,
    merged: dict[str, Any],
    *,
    origin: str,
    quote: str,
    terms: list[NameReplacement],
) -> Result[dict[str, Any]]:
    """The statement's fields after the API rules (API_CONTRACT.md → Intent), or the first
    problem with the field it is about."""
    if merged.get("kind") not in {k.value for k in IntentKind}:
        return _invalid("kind", BAD_KIND)
    scope = merged.get("scope") or "process"
    if scope not in SCOPES:
        return _invalid("scope", BAD_SCOPE)
    steps, phases = _map_places(session, engagement_id)
    if scope == "step" and merged.get("element_stable_key") not in steps:
        return _invalid("element_stable_key", BAD_STEP)
    if scope == "phase" and merged.get("phase_name") not in phases:
        return _invalid("phase_name", BAD_PHASE)
    text = (merged.get("text") or "").strip()
    if not text or len(text) > MAX_TEXT or "\n" in text:
        return _invalid("text", BAD_TEXT)
    if grounding.scan_redaction_terms(text, [t.term for t in terms]):
        return _invalid("text", NAMED)
    metric = merged.get("metric")
    target = (merged.get("comparator"), merged.get("target_value"), merged.get("unit"))
    if metric is None:
        if any(v is not None for v in target):
            return _invalid("metric", TARGET_WITHOUT_METRIC)
    else:
        if metric not in {m.value for m in IntentMetric}:
            return _invalid("metric", BAD_METRIC)
        comparator, value, unit = target
        if (comparator not in COMPARATORS or value is None or value < 0 or unit not in UNITS
                or not _unit_fits(metric, str(unit))):  # fmt: skip
            return _invalid("target_value", NEED_TARGET)
        if origin == IntentOrigin.DOCUMENT.value and not _in_quote(float(value), quote):
            return _invalid("target_value", NOT_IN_QUOTE)
    fields = {
        "scope": scope, "kind": merged["kind"], "text": text, "metric": metric,
        "comparator": target[0], "target_value": target[1], "unit": target[2],
        "element_stable_key": merged.get("element_stable_key") if scope == "step" else None,
        "phase_name": merged.get("phase_name") if scope == "phase" else None,
    }  # fmt: skip
    if origin == IntentOrigin.OWNER_STATED.value:
        roles = {r.id for r in engagements_repo.list_roles(session, engagement_id)
                 if not r.is_system}  # fmt: skip
        if merged.get("owner_role_id") not in roles:
            return _invalid("owner_role_id", BAD_OWNER)
        try:
            stated = date.fromisoformat(str(merged.get("stated_on") or ""))
        except ValueError:
            return _invalid("stated_on", BAD_DATE)
        if stated > date.today():
            return _invalid("stated_on", BAD_DATE)
        fields |= {"owner_role_id": merged["owner_role_id"], "stated_on": stated.isoformat()}
    return Ok(fields)


def list_intent(sessions: Sessions, engagement_id: str) -> Result[list[IntentView]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(_views(session, engagement_id, repo.for_engagement(session, engagement_id)))


def add_owner_stated(
    config: AppConfig, sessions: Sessions, engagement_id: str, body: IntentFields
) -> Result[IntentView]:
    """A statement an owner gave Eric (a meeting, an email): labelled "Target set by <role>"."""
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        terms = redaction.name_replacements(session, engagement_id)
        match _check(session, engagement_id, body.model_dump(),
                     origin=IntentOrigin.OWNER_STATED.value, quote="", terms=terms):  # fmt: skip
            case Err() as err:
                return err
            case Ok(value=fields):
                pass
        row = repo.add(session, {
            **fields, "engagement_id": engagement_id, "origin": IntentOrigin.OWNER_STATED.value,
            "verification_status": VerificationStatus.VERIFIED.value, "status": "confirmed",
            "segment_ids": [], "quote": "", "note": "",
        })  # fmt: skip
        view = _views(session, engagement_id, [row])[0]
        audit.record(session, actor=actor_name(config), action="Added intent statement",
                     target_type="intent", target_id=row.id, engagement_id=engagement_id,
                     after={"kind": view.kind, "text": view.text, "label": view.label})  # fmt: skip
        return Ok(view)


def update_intent(
    config: AppConfig, sessions: Sessions, intent_id: str, patch: IntentPatch
) -> Result[IntentView]:
    """Confirm, dismiss or reopen a statement, edit it, or note why."""
    with session_scope(sessions) as session:
        row = repo.get(session, intent_id)
        if row is None:
            return Err(ErrorKind.NOT_FOUND, INTENT_MISSING)
        changes: dict[str, Any] = {}
        if patch.edits is not None:
            edits = patch.edits.model_dump(exclude_unset=True)
            document = row.origin == IntentOrigin.DOCUMENT.value
            if document and ({"owner_role_id", "stated_on"} & set(edits)):
                return _invalid("edits", OWNER_ON_DOCUMENT)
            merged = row.model_dump() | edits
            terms = redaction.name_replacements(session, row.engagement_id)
            match _check(session, row.engagement_id, merged, origin=row.origin, quote=row.quote,
                         terms=terms):  # fmt: skip
                case Err() as err:
                    return err
                case Ok(value=fields):
                    changes |= {k: v for k, v in fields.items() if getattr(row, k) != v}
        if patch.note is not None:
            note = patch.note.strip()
            if len(note) > MAX_NOTE or "\n" in note:
                return _invalid("note", BAD_NOTE)
            changes["note"] = note
        if patch.status is not None:
            if patch.status not in STATUSES:
                return _invalid("status", BAD_STATUS)
            rejected = row.verification_status == VerificationStatus.REJECTED.value
            if patch.status == "confirmed" and rejected:
                return Err(ErrorKind.CONFLICT, REJECTED)
            if patch.status != row.status:
                changes["status"] = patch.status
        if not changes:
            return Ok(_views(session, row.engagement_id, [row])[0])
        before = {k: getattr(row, k) for k in changes}
        updated = repo.update(session, intent_id, changes)
        action = (STATUS_ACTIONS[patch.status] if "status" in changes and patch.status
                  else "Edited intent statement")  # fmt: skip
        audit.record(session, actor=actor_name(config), action=action, target_type="intent",
                     target_id=intent_id, engagement_id=row.engagement_id, before=before,
                     after=changes)  # fmt: skip
        return Ok(_views(session, row.engagement_id, [updated])[0])


def delete_intent(config: AppConfig, sessions: Sessions, intent_id: str) -> Result[None]:
    with session_scope(sessions) as session:
        row = repo.get(session, intent_id)
        if row is None:
            return Err(ErrorKind.NOT_FOUND, INTENT_MISSING)
        if row.origin == IntentOrigin.DOCUMENT.value:
            return Err(ErrorKind.CONFLICT, DOCUMENT_DELETE)
        repo.delete(session, intent_id)
        audit.record(session, actor=actor_name(config), action="Deleted intent statement",
                     target_type="intent", target_id=intent_id, engagement_id=row.engagement_id,
                     before={"kind": row.kind, "text": row.text})  # fmt: skip
        return Ok(None)
