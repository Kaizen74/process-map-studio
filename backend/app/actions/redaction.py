"""Names to hide (PRD §3.8 G10): the redaction list and the rules for applying it.

Every response that returns source text hides the engagement's name terms, except the three
owner-only places: the speaker-mapping card, this redaction list, and the correction editor.
Confidential terms (scope card) share the table but are not name terms: they only restrict what is
sent to web research (DECISIONS 2026-09-26).
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import NameReplacement, RedactionTermCreate, RedactionTermView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import redaction as repo
from app.services import grounding
from app.services.grounding import DEFAULT_REPLACEMENT

Sessions = sessionmaker[Session]

NAME_ORIGINS = repo.NAME_ORIGINS
TERM_MISSING = "That name isn't on the list any more."
DUPLICATE = "That name is already on the list."
BAD_TERM = "Please enter a name of up to 120 characters, on one line."
BAD_REPLACEMENT = "The replacement can be up to 80 characters, on one line."


def name_replacements(session: Session, engagement_id: str) -> list[NameReplacement]:
    """The engagement's name terms with what to show instead, for `grounding.redact_text`."""
    return [
        NameReplacement(term=t.term, replacement=t.replacement or DEFAULT_REPLACEMENT)
        for t in repo.list_terms(session, engagement_id, NAME_ORIGINS)
    ]


def hide(text: str, terms: list[NameReplacement]) -> str:
    return grounding.redact_text(text, terms).text if terms and text else text


def set_speaker_term(session: Session, engagement_id: str, label: str, replacement: str) -> None:
    """A name-like speaker label is on the list, shown as its mapped role (or "[name]")."""
    existing = repo.find(session, engagement_id, label, NAME_ORIGINS)
    if existing is None:
        repo.add(
            session,
            engagement_id=engagement_id,
            term=label,
            replacement=replacement,
            origin="speaker_map",
        )
    else:
        repo.set_replacement(session, existing.id, replacement)


def list_terms(sessions: Sessions, engagement_id: str) -> Result[list[RedactionTermView]]:
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(repo.list_terms(session, engagement_id, NAME_ORIGINS))


def add_term(
    config: AppConfig, sessions: Sessions, engagement_id: str, data: RedactionTermCreate
) -> Result[RedactionTermView]:
    term = " ".join(data.term.split())
    replacement = " ".join(data.replacement.split())
    if not term or len(term) > 120 or "\n" in data.term:
        return Err(ErrorKind.VALIDATION, BAD_TERM, {"field": "term"})
    if len(replacement) > 80 or "\n" in data.replacement:
        return Err(ErrorKind.VALIDATION, BAD_REPLACEMENT, {"field": "replacement"})
    actor = actor_name(config)
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if repo.find(session, engagement_id, term, NAME_ORIGINS) is not None:
            return Err(ErrorKind.CONFLICT, DUPLICATE, {"field": "term"})
        view = repo.add(
            session,
            engagement_id=engagement_id,
            term=term,
            replacement=replacement or DEFAULT_REPLACEMENT,
            origin="manual",
        )
        # The audit log is shown outside the owner-only places, so it never holds the name.
        audit.record(
            session,
            actor=actor,
            action="Added a name to hide",
            target_type="redaction_term",
            target_id=view.id,
            engagement_id=engagement_id,
        )
    return Ok(view)


def delete_term(config: AppConfig, sessions: Sessions, term_id: str) -> Result[None]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        term = repo.get(session, term_id)
        if term is None or term.origin not in NAME_ORIGINS:
            return Err(ErrorKind.NOT_FOUND, TERM_MISSING)
        repo.delete(session, term_id)
        audit.record(
            session,
            actor=actor,
            action="Removed a name to hide",
            target_type="redaction_term",
            target_id=term_id,
            engagement_id=term.engagement_id,
        )
    return Ok(None)
