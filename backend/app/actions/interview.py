"""Interview tools for one engagement (PRD §3.12.8, Appendix F.8; phase P4c).

C5a: interviewee profiles — whose interview a tailored guide is for: a role, function or
stakeholder group, never a person (constraint 10). Every change writes an audit row.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import InterviewType
from app.domain.interview import ProfileInput, ProfilePatch, ProfileView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import interview as interview_repo
from app.services import grounding

Sessions = sessionmaker[Session]

ENGAGEMENT_MISSING = "That engagement doesn't exist."
PROFILE_MISSING = "That interviewee profile doesn't exist."
MAX_TEXT = 120
TEXTS = {"stakeholder_group": "The stakeholder group", "referred_by_role": "Referred by"}
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _check(session: Session, engagement_id: str, profile_id: str | None,
           fields: dict[str, Any]) -> Result[dict[str, Any]]:  # fmt: skip
    """The profile's fields, tidied, or the first problem naming its field."""
    if fields["interview_type"] not in {t.value for t in InterviewType}:
        return _invalid("interview_type", "Choose landscape, practice or follow-up.")
    roles = {r.id for r in engagements_repo.list_roles(session, engagement_id)}
    if fields["role_id"] is not None and fields["role_id"] not in roles:
        return _invalid("role_id", "Choose one of this engagement's roles.")
    hidden = [t.term for t in redaction.name_replacements(session, engagement_id)]
    for field, words in TEXTS.items():
        text = str(fields[field] or "").strip()
        if len(text) > MAX_TEXT or "\n" in text:
            return _invalid(field, f"{words} can be up to {MAX_TEXT} characters on one line.")
        if grounding.scan_redaction_terms(text, hidden):  # the name itself is never echoed
            return _invalid(field, HIDDEN_NAME.format(what=words))
        fields[field] = text
    if fields["role_id"] is None and not fields["stakeholder_group"]:
        return _invalid(
            "role_id", "Say whose interview this is: choose a role or name the stakeholder group."
        )
    previous = fields["previous_profile_id"]
    if previous is not None:
        earlier = interview_repo.profile(session, previous)
        if earlier is None or earlier.engagement_id != engagement_id or previous == profile_id:
            return _invalid(
                "previous_profile_id", "Choose an earlier interview in this engagement."
            )
    return Ok(fields)


def list_profiles(sessions: Sessions, engagement_id: str) -> Result[list[ProfileView]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(interview_repo.profiles(session, engagement_id))


def add_profile(
    config: AppConfig, sessions: Sessions, engagement_id: str, body: ProfileInput
) -> Result[ProfileView]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        checked = _check(session, engagement_id, None, body.model_dump())
        if isinstance(checked, Err):
            return checked
        created = interview_repo.add_profile(session, engagement_id, checked.value)
        audit.record(session, actor=actor_name(config), action="Added interviewee profile",
                     target_type="profile", target_id=created.id, engagement_id=engagement_id,
                     after=checked.value)  # fmt: skip
        return Ok(created)


def edit_profile(
    config: AppConfig, sessions: Sessions, profile_id: str, patch: ProfilePatch
) -> Result[ProfileView]:
    with session_scope(sessions) as session:
        before = interview_repo.profile(session, profile_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, PROFILE_MISSING)
        current = before.model_dump(include=set(ProfileInput.model_fields))
        sent = {name: getattr(patch, name) for name in patch.model_fields_set}
        for name in ("stakeholder_group", "referred_by_role", "interview_type"):
            if name in sent and sent[name] is None:
                sent[name] = ""
        checked = _check(session, before.engagement_id, profile_id, current | sent)
        if isinstance(checked, Err):
            return checked
        changed = {k: v for k, v in checked.value.items() if v != current[k]}
        if not changed:
            return Ok(before)
        updated = interview_repo.update_profile(session, profile_id, changed)
        audit.record(session, actor=actor_name(config), action="Edited interviewee profile",
                     target_type="profile", target_id=profile_id,
                     engagement_id=before.engagement_id,
                     before={k: current[k] for k in changed}, after=changed)  # fmt: skip
        return Ok(updated)
