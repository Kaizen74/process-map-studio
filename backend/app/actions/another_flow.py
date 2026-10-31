"""Map another flow from these sources (2026-10-28, Eric's cargo manual; DECISIONS 81).

One engagement maps one flow. A manual that describes several (import, export, transfer) is mapped
once per flow: this starts the next engagement with the same documents as already read (no reading
again, no AI call), the same roles, names to hide and mapping conventions. Eric gives it its own
name, trigger and end point. Nothing of the first engagement's map is copied: each flow is drafted
and reviewed on its own.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.actions.engagements import ENGAGEMENT_MISSING, actor_name, clean_scope
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import AnotherFlow, EngagementCreate, EngagementView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as repo
from app.repositories import redaction as redaction_repo
from app.repositories import sources as sources_repo
from app.services import images as pictures

Sessions = sessionmaker[Session]

CARRIED = ("process_name", "in_scope_roles", "industry", "adjacent_industries")
STILL_READING = "{name} is still being read. Try again when every document is ready."
NOT_THESE_ROLES = "Choose roles of this engagement."


def _copy_file(old: str, new: Path, data_root: Path) -> None:
    """Copy a stored file inside the data folder (never anything outside it)."""
    source = Path(old).resolve()
    if source.is_relative_to(data_root) and source.is_file():
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, new)


def another_flow(
    config: AppConfig, sessions: Sessions, engagement_id: str, data: AnotherFlow
) -> Result[EngagementView]:
    with session_scope(sessions) as session:
        first = repo.get(session, engagement_id)
        files = sources_repo.files_for_engagement(session, engagement_id)
    if first is None:
        return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
    # A copy of a document still being read would never be read (no job is queued for it).
    reading = next((name for _, _, name, status in files if status == "pending"), None)
    if reading is not None:
        return Err(ErrorKind.CONFLICT, STILL_READING.format(name=reading))
    if data.role_ids is not None:
        with session_scope(sessions) as session:
            known = repo.role_ids(session, engagement_id)
        if not set(data.role_ids) <= known:
            return Err(ErrorKind.VALIDATION, NOT_THESE_ROLES, {"field": "role_ids"})
    carried = {k: getattr(first, k) for k in CARRIED}
    scope = EngagementCreate(
        **{**carried, "conventions": first.conventions.model_dump()},
        **data.model_dump(exclude_unset=True, exclude={"role_ids"}),
    )
    match clean_scope(scope, require_name=True):
        case Err() as err:
            return err
        case Ok(value=fields):
            pass
    actor = actor_name(config)
    data_root = config.data_dir.resolve()
    with session_scope(sessions) as session:
        view = repo.create(session, fields)
        roles = repo.copy_roles(session, engagement_id, view.id, data.role_ids)
        terms = redaction_repo.copy_terms(session, engagement_id, view.id)
        copied = 0
        for source_id, fmt, _name, _status in sources_repo.files_for_engagement(
            session, engagement_id
        ):
            copy_id = str(uuid.uuid4())
            target = config.data_dir / "sources" / view.id / f"{copy_id}.{fmt}"
            done = sources_repo.copy_source(
                session, source_id, (copy_id, view.id, str(target)), roles
            )
            if done is None:
                continue
            _copy_file(done.old_path, target, data_root)
            for number, (path, page, caption) in enumerate(done.pictures, start=1):
                picture = (
                    config.data_dir
                    / "images"
                    / view.id
                    / f"{copy_id}-p{page}-{number}{Path(path).suffix}"
                )
                _copy_file(path, picture, data_root)
                _copy_file(
                    str(pictures.thumb_path(path)), pictures.thumb_path(str(picture)), data_root
                )
                sources_repo.add_suggested_image(
                    session, source_id=copy_id, stored_path=str(picture), page=page, caption=caption
                )
            copied += 1
        audit.record(
            session,
            actor=actor,
            action="Started another flow from these sources",
            target_type="engagement",
            target_id=view.id,
            engagement_id=view.id,
            after={
                **fields,
                "from_engagement": first.name,
                "sources": copied,
                "roles": len(roles),
                "names_to_hide": terms,
            },
        )
        created = repo.get(session, view.id)
    assert created is not None
    return Ok(created)
