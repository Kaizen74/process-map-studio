"""Engagement, scope-card and role actions (PRD §4, §5.4 Setup).

Validation and plain-language messages live here; every change writes an audit row whose actor
is the owner name from Settings.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions.settings import effective_settings
from app.config import AppConfig
from app.db import session_scope
from app.domain.compass import CompassLink, HandoffPrinciple
from app.domain.models import (
    CONVENTION_CHOICES,
    EngagementCreate,
    EngagementSummary,
    EngagementView,
    MappingConventions,
    RoleCreate,
    RolePatch,
    RoleUses,
    RoleView,
    ScopeFields,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as repo
from app.repositories import redaction as redaction_repo
from app.repositories import testing as testing_repo
from app.services import compass as compass_service

Sessions = sessionmaker[Session]

ENGAGEMENT_MISSING = "That engagement doesn't exist. It may have been deleted."
NOT_SCOPE = {"compass", "role_names", "reference_engagement_id"}  # create only, not the card
ROLE_MISSING = "That role doesn't exist. It may have been removed."
REFERENCE_MISSING = "The engagement to start from doesn't exist. It may have been deleted."
COUNTRY_FROM_HANDOFF = (
    "The country comes from the Capability Compass hand-off, so it can't be changed here."
)
# What starting from another country copies of its scope card (DECISIONS 98), with conventions.
REFERENCE_FIELDS = ("process_name", "trigger", "end_point", "process_kpi", "in_scope_roles")
TEXT_LIMIT = 2000
LIST_LIMIT = 50
ITEM_LIMIT = 120

_LABELS = {
    "conventions": "Mapping conventions",
    "name": "Engagement name",
    "country": "Country",
    "process_name": "Process name",
    "trigger": "Trigger",
    "end_point": "End point",
    "out_of_scope": "Out of scope",
    "process_kpi": "Process KPI",
    "industry": "Industry",
    "in_scope_roles": "In-scope roles",
    "adjacent_industries": "Adjacent industries",
    "confidential_terms": "Confidential terms",
    "trigger_external": "Starts outside the organisation",
    "end_point_external": "Ends outside the organisation",
    "every_flow": "Map every flow in these documents",
}
_LIST_FIELDS = {"in_scope_roles", "adjacent_industries", "confidential_terms"}
_FLAG_FIELDS = {"trigger_external", "end_point_external", "every_flow"}


def _invalid_conflict(field: str, message: str) -> Err:
    return Err(ErrorKind.CONFLICT, message, {"field": field})


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _clean_list(field: str, values: list[str]) -> Result[list[str]]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = raw.strip()
        if not item:
            continue
        if len(item) > ITEM_LIMIT or any(ch in item for ch in "\r\n\t"):
            return _invalid(
                field,
                f"{_LABELS[field]}: each entry must be one line of up to {ITEM_LIMIT} characters.",
            )
        if item.casefold() not in seen:
            seen.add(item.casefold())
            cleaned.append(item)
    if len(cleaned) > LIST_LIMIT:
        return _invalid(field, f"{_LABELS[field]}: at most {LIST_LIMIT} entries.")
    return Ok(cleaned)


CONVENTION_WORDS = {
    "granularity": "Choose coarse, standard or fine.",
    "label_style": "Choose standard wording or SME wording.",
    "phase_naming": "Choose SME terms or standard terms.",
}


def _clean_conventions(value: dict[str, str]) -> Result[dict[str, str]]:
    """The whole tier 2 settings object (C7a): every field known, every value one of its choices;
    a field not sent keeps its default."""
    for name in value:
        if name not in CONVENTION_CHOICES:
            return _invalid(f"conventions.{name}", "That isn't a mapping convention.")
    for name, choices in CONVENTION_CHOICES.items():
        if name in value and value[name] not in choices:
            return _invalid(f"conventions.{name}", CONVENTION_WORDS[name])
    return Ok(MappingConventions.model_validate(value).model_dump())


def clean_scope(fields: ScopeFields, *, require_name: bool) -> Result[dict[str, Any]]:
    """Validate and tidy the scope-card fields that were sent."""
    sent = fields.model_dump(exclude_unset=True, exclude=NOT_SCOPE)
    cleaned: dict[str, Any] = {}
    for field, value in sent.items():
        if value is None:
            return _invalid(field, f"{_LABELS[field]} can't be empty.")
        if field == "conventions":
            match _clean_conventions(value):
                case Err() as err:
                    return err
                case Ok(value=conventions):
                    cleaned[field] = conventions
            continue
        if field in _FLAG_FIELDS:
            if not isinstance(value, bool):
                return _invalid(field, f"{_LABELS[field]}: choose yes or no.")
            cleaned[field] = value
            continue
        if field in _LIST_FIELDS:
            match _clean_list(field, value):
                case Err() as err:
                    return err
                case Ok(value=items):
                    cleaned[field] = items
            continue
        text = str(value).strip()
        if field == "country" and (len(text) > ITEM_LIMIT or "\n" in text):
            return _invalid("country", "Country: one line of up to 120 characters.")
        if field == "name":
            if not text or len(text) > ITEM_LIMIT or "\n" in text:
                return _invalid("name", "Please give the engagement a name (up to 120 characters).")
        elif len(text) > TEXT_LIMIT:
            return _invalid(field, f"{_LABELS[field]}: at most {TEXT_LIMIT} characters.")
        cleaned[field] = text
    if require_name and "name" not in cleaned:
        return _invalid("name", "Please give the engagement a name (up to 120 characters).")
    return Ok(cleaned)


def actor_name(config: AppConfig) -> str:
    """Who is making changes: the owner name from Settings (used for audit rows)."""
    match effective_settings(config):
        case Ok(value=values):
            return values["OWNER_NAME"]
        case Err():
            return "Owner"


def _in_session[T](sessions: Sessions, work: Callable[[Session], Result[T]]) -> Result[T]:
    """Run work in one unit of work; an Err result rolls everything back."""
    with session_scope(sessions) as session:
        result = work(session)
        if isinstance(result, Err):
            session.rollback()
        return result


# --- Engagements ------------------------------------------------------------------------------


def _from_handoff(
    data: EngagementCreate,
) -> Result[tuple[CompassLink | None, list[HandoffPrinciple]]]:
    """The link to keep and the principles to test, read again from the file (DECISIONS 95)."""
    if data.compass is None:
        return Ok((None, []))
    match compass_service.read_handoff(data.compass.handoff):
        case Err(kind=kind, message=message):
            return Err(kind, message, {"field": "compass"})
        case Ok(value=preview):
            pass
    match compass_service.choose_pilot(preview, data.compass.pilot_ref):
        case Err() as err:
            return err
        case Ok(value=pilot):
            pass
    link = CompassLink(
        key=preview.key, pilot_ref=pilot.ref, cluster_ref=pilot.cluster_ref,
        cluster_name=pilot.cluster_name, cell_refs=pilot.cell_refs,
        interview_prompts=pilot.interview_prompts, ready=preview.ready,
        generated_at=preview.generated_at, country=preview.country,
    )  # fmt: skip
    return Ok((link, preview.principles))


def _lane_names(names: list[str] | None) -> Result[list[str]]:
    cleaned: list[str] = []
    for raw in names or []:
        if not raw.strip():
            continue
        match _clean_role_name(raw):
            case Err() as err:
                return err
            case Ok(value=name):
                if name.casefold() not in {n.casefold() for n in cleaned}:
                    cleaned.append(name)
    return Ok(cleaned)


def create_engagement(
    config: AppConfig, sessions: Sessions, data: EngagementCreate
) -> Result[EngagementView]:
    match clean_scope(data, require_name=True):
        case Err() as err:
            return err
        case Ok(value=fields):
            pass
    match _from_handoff(data):
        case Err() as err:
            return err
        case Ok(value=(link, principles)):
            pass
    match _lane_names(data.role_names):
        case Err() as err:
            return err
        case Ok(value=lanes):
            pass
    if link is not None:
        fields["country"] = link.country  # from the packet, as received (DECISIONS 98)
    actor = actor_name(config)
    reference_id = data.reference_engagement_id

    def work(session: Session) -> Result[EngagementView]:
        if reference_id is not None:
            reference = repo.get(session, reference_id)
            if reference is None:
                return Err(ErrorKind.NOT_FOUND, REFERENCE_MISSING,
                           {"field": "reference_engagement_id"})  # fmt: skip
            # The other country's scope card fields the request left out, and its conventions:
            # nothing else crosses (no source, alias, name to hide, map or code).
            for name in REFERENCE_FIELDS:
                if name not in data.model_fields_set:
                    fields[name] = getattr(reference, name)
            fields["conventions"] = reference.conventions.model_dump()
        view = repo.create(session, fields, link, reference_id)
        for name in lanes:
            repo.create_role(session, view.id, name, [], False)
        for principle in principles:
            testing_repo.add(session, view.id, ref=principle.ref, text=principle.text,
                             refuted_by=principle.refuted_by, origin="compass")  # fmt: skip
        after: dict[str, Any] = dict(fields)
        if link is not None:
            after["compass"] = {"key": link.key, "pilot_ref": link.pilot_ref,
                                "cluster_ref": link.cluster_ref}  # fmt: skip
            after["roles"], after["testing"] = len(lanes), len(principles)
        elif lanes:
            after["roles"] = len(lanes)
        if reference_id is not None:
            after["reference_engagement_id"] = reference_id
            after["roles"] = len(lanes)
        audit.record(
            session,
            actor=actor,
            action="Created engagement",
            target_type="engagement",
            target_id=view.id,
            engagement_id=view.id,
            after=after,
        )
        return Ok(view)

    return _in_session(sessions, work)


def list_engagements(sessions: Sessions) -> Result[list[EngagementSummary]]:
    with session_scope(sessions) as session:
        return Ok(repo.list_summaries(session))


def get_engagement(sessions: Sessions, engagement_id: str) -> Result[EngagementView]:
    with session_scope(sessions) as session:
        view = repo.get(session, engagement_id)
    return Ok(view) if view else Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)


def update_engagement(
    config: AppConfig, sessions: Sessions, engagement_id: str, data: ScopeFields
) -> Result[EngagementView]:
    match clean_scope(data, require_name=False):
        case Err() as err:
            return err
        case Ok(value=fields):
            pass
    actor = actor_name(config)

    def work(session: Session) -> Result[EngagementView]:
        before = repo.get(session, engagement_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if before.compass is not None and fields.get("country", before.country) != before.country:
            return _invalid_conflict("country", COUNTRY_FROM_HANDOFF)
        view = repo.update(session, engagement_id, fields)
        assert view is not None
        old = before.model_dump()
        changed = {k: v for k, v in fields.items() if old.get(k) != v}
        if changed:
            audit.record(
                session,
                actor=actor,
                action="Edited process scope",
                target_type="engagement",
                target_id=engagement_id,
                engagement_id=engagement_id,
                before={k: old.get(k) for k in changed},
                after=changed,
            )
        return Ok(view)

    return _in_session(sessions, work)


def delete_engagement(config: AppConfig, sessions: Sessions, engagement_id: str) -> Result[None]:
    """Remove the engagement, all its rows (cascade) and its files."""
    with session_scope(sessions) as session:
        if not repo.delete(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
    left = []
    for folder in (
        config.data_dir / "sources" / engagement_id,
        config.data_dir / "images" / engagement_id,
    ):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            if folder.exists():
                left.append(str(folder))
    if left:
        return Err(
            ErrorKind.IO,
            "The engagement was deleted, but some of its files couldn't be removed. "
            "Close any program using them and delete these folders by hand: " + ", ".join(left),
            {"folders": left},
        )
    return Ok(None)


# --- Roles and lanes --------------------------------------------------------------------------


def _clean_role_name(name: str) -> Result[str]:
    text = name.strip()
    if not text or len(text) > 80 or "\n" in text:
        return _invalid("name", "Please give the role a name (up to 80 characters).")
    return Ok(text)


def _clean_aliases(aliases: list[str]) -> Result[list[str]]:
    cleaned: list[str] = []
    for alias in aliases:
        item = alias.strip()
        if item and item.casefold() not in {a.casefold() for a in cleaned}:
            if len(item) > 80 or "\n" in item:
                return _invalid("aliases", "Each alias must be one line of up to 80 characters.")
            cleaned.append(item)
    return Ok(cleaned)


def list_roles(sessions: Sessions, engagement_id: str) -> Result[list[RoleView]]:
    with session_scope(sessions) as session:
        if not repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(repo.list_roles(session, engagement_id))


def create_role(
    config: AppConfig, sessions: Sessions, engagement_id: str, data: RoleCreate
) -> Result[RoleView]:
    match _clean_role_name(data.name):
        case Err() as err:
            return err
        case Ok(value=name):
            pass
    match _clean_aliases(data.aliases):
        case Err() as err:
            return err
        case Ok(value=aliases):
            pass
    actor = actor_name(config)

    def work(session: Session) -> Result[RoleView]:
        if not repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if repo.role_name_taken(session, engagement_id, name):
            return Err(
                ErrorKind.CONFLICT, f"There is already a role called {name}.", {"field": "name"}
            )
        role = repo.create_role(session, engagement_id, name, aliases, data.is_system)
        repo.touch(session, engagement_id)
        audit.record(
            session,
            actor=actor,
            action="Added role",
            target_type="role",
            target_id=role.id,
            engagement_id=engagement_id,
            after=role.model_dump(exclude={"id", "engagement_id"}),
        )
        return Ok(role)

    return _in_session(sessions, work)


def update_role(
    config: AppConfig, sessions: Sessions, role_id: str, data: RolePatch
) -> Result[RoleView]:
    sent = data.model_dump(exclude_unset=True)
    fields: dict[str, Any] = {}
    if "name" in sent:
        match _clean_role_name(sent["name"] or ""):
            case Err() as err:
                return err
            case Ok(value=name):
                fields["name"] = name
    if "aliases" in sent:
        match _clean_aliases(sent["aliases"] or []):
            case Err() as err:
                return err
            case Ok(value=aliases):
                fields["aliases"] = aliases
    if sent.get("is_system") is not None:
        fields["is_system"] = bool(sent["is_system"])
    if "lane_order" in sent:
        if not isinstance(sent["lane_order"], int) or sent["lane_order"] < 1:
            return _invalid("lane_order", "Lane order must be 1 or more.")
        fields["lane_order"] = sent["lane_order"]
    actor = actor_name(config)

    def work(session: Session) -> Result[RoleView]:
        before = repo.get_role(session, role_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, ROLE_MISSING)
        if "name" in fields and repo.role_name_taken(
            session, before.engagement_id, fields["name"], exclude_id=role_id
        ):
            return Err(
                ErrorKind.CONFLICT,
                f"There is already a role called {fields['name']}.",
                {"field": "name"},
            )
        role = repo.update_role(session, role_id, fields)
        if "name" in fields and fields["name"] != before.name:
            # Names shown as this role now show its new name (PRD §3.8 G10).
            redaction_repo.replace_replacement(
                session,
                before.engagement_id,
                before.name,
                fields["name"],
                redaction_repo.NAME_ORIGINS,
            )
        assert role is not None
        repo.touch(session, before.engagement_id)
        audit.record(
            session,
            actor=actor,
            action="Edited role",
            target_type="role",
            target_id=role_id,
            engagement_id=before.engagement_id,
            before=before.model_dump(exclude={"id", "engagement_id"}),
            after=role.model_dump(exclude={"id", "engagement_id"}),
        )
        return Ok(role)

    return _in_session(sessions, work)


def role_in_use(name: str, uses: RoleUses) -> str:
    """Why a role can't be removed, in plain words, or "" when nothing uses it (DECISIONS 93)."""
    reasons = []
    if uses.steps:
        n = len(uses.steps)
        shown = [f"“{label}”" for label in uses.steps[:2]]
        listed = ", ".join(shown) + (f" and {n - 2} more" if n > 2 else "")
        reasons.append(f"{n} {'step uses' if n == 1 else 'steps use'} it ({listed})")
    for count, words in (
        (uses.speakers, "a speaker in an interview is mapped to it"),
        (uses.profiles, "an interviewee profile names it"),
        (uses.events, "a system log's events are mapped to it"),
        (uses.costs, "it has an hourly cost"),
        (uses.intents, "an intent statement names it as owner"),
        (uses.discrepancies, "a discrepancy names it as decision owner"),
    ):
        if count:
            reasons.append(words)
    return f"{name} can't be removed: {'; '.join(reasons)}." if reasons else ""


def delete_role(config: AppConfig, sessions: Sessions, role_id: str) -> Result[None]:
    """Remove a role nothing uses; the lanes below move up (DECISIONS 93)."""
    actor = actor_name(config)

    def work(session: Session) -> Result[None]:
        role = repo.get_role(session, role_id)
        if role is None:
            return Err(ErrorKind.NOT_FOUND, ROLE_MISSING)
        if why := role_in_use(role.name, repo.role_uses(session, role_id)):
            return Err(ErrorKind.CONFLICT, why)
        repo.delete_role(session, role_id)
        repo.touch(session, role.engagement_id)
        audit.record(
            session,
            actor=actor,
            action="Removed role",
            target_type="role",
            target_id=role_id,
            engagement_id=role.engagement_id,
            before=role.model_dump(exclude={"id", "engagement_id"}),
            after=None,
        )
        return Ok(None)

    return _in_session(sessions, work)
