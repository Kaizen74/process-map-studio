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
from app.domain.models import (
    EngagementCreate,
    EngagementSummary,
    EngagementView,
    RoleCreate,
    RolePatch,
    RoleView,
    ScopeFields,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as repo

Sessions = sessionmaker[Session]

ENGAGEMENT_MISSING = "That engagement doesn't exist. It may have been deleted."
ROLE_MISSING = "That role doesn't exist. It may have been removed."
TEXT_LIMIT = 2000
LIST_LIMIT = 50
ITEM_LIMIT = 120

_LABELS = {
    "name": "Engagement name",
    "process_name": "Process name",
    "trigger": "Trigger",
    "end_point": "End point",
    "out_of_scope": "Out of scope",
    "process_kpi": "Process KPI",
    "industry": "Industry",
    "in_scope_roles": "In-scope roles",
    "adjacent_industries": "Adjacent industries",
    "confidential_terms": "Confidential terms",
}
_LIST_FIELDS = {"in_scope_roles", "adjacent_industries", "confidential_terms"}


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


def clean_scope(fields: ScopeFields, *, require_name: bool) -> Result[dict[str, Any]]:
    """Validate and tidy the scope-card fields that were sent."""
    sent = fields.model_dump(exclude_unset=True)
    cleaned: dict[str, Any] = {}
    for field, value in sent.items():
        if value is None:
            return _invalid(field, f"{_LABELS[field]} can't be empty.")
        if field in _LIST_FIELDS:
            match _clean_list(field, value):
                case Err() as err:
                    return err
                case Ok(value=items):
                    cleaned[field] = items
            continue
        text = str(value).strip()
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


def create_engagement(
    config: AppConfig, sessions: Sessions, data: EngagementCreate
) -> Result[EngagementView]:
    match clean_scope(data, require_name=True):
        case Err() as err:
            return err
        case Ok(value=fields):
            pass
    actor = actor_name(config)

    def work(session: Session) -> Result[EngagementView]:
        view = repo.create(session, fields)
        audit.record(
            session,
            actor=actor,
            action="Created engagement",
            target_type="engagement",
            target_id=view.id,
            engagement_id=view.id,
            after=fields,
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
