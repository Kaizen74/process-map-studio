"""Map this process in another country (PRD §3.19; DECISIONS 98): a new engagement for another
country, started from this one's scope card, conventions and lane names. Unlike Map another flow,
no document, transcript, map, code, role alias or name to hide is copied: the new country has its
own sources."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions.engagements import (
    ENGAGEMENT_MISSING,
    REFERENCE_FIELDS,
    actor_name,
    clean_scope,
)
from app.config import AppConfig
from app.db import session_scope
from app.domain.compass import HandoffPreview, SameProcess
from app.domain.models import AnotherCountry, EngagementCreate, EngagementView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as repo
from app.repositories import versions as versions_repo
from app.services import compass as compass_service

Sessions = sessionmaker[Session]

NOT_PUBLISHED = (
    "Publish a version of this engagement first: another country starts from a published map."
)
NO_COUNTRY = "Type the country this map will cover."
SAME_COUNTRY = "This engagement already covers {country}."
NOT_THESE_ROLES = "Choose roles of this engagement."


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def another_country(
    config: AppConfig, sessions: Sessions, engagement_id: str, data: AnotherCountry
) -> Result[EngagementView]:
    country = data.country.strip()
    if not country:
        return _invalid("country", NO_COUNTRY)
    with session_scope(sessions) as session:
        first = repo.get(session, engagement_id)
        if first is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if versions_repo.latest_published(session, engagement_id) is None:
            return Err(ErrorKind.CONFLICT, NOT_PUBLISHED)
        if first.country and first.country.casefold() == country.casefold():
            return _invalid("country", SAME_COUNTRY.format(country=first.country))
        if data.role_ids is not None and not set(data.role_ids) <= repo.role_ids(
            session, engagement_id
        ):
            return _invalid("role_ids", NOT_THESE_ROLES)
        lanes = repo.lane_names(session, engagement_id, data.role_ids)
        name = (data.name or "").strip() or f"{first.process_name or first.name} — {country}"
        scope = EngagementCreate(
            name=name, country=country, conventions=first.conventions.model_dump(),
            **{k: getattr(first, k) for k in REFERENCE_FIELDS},
        )  # fmt: skip
        match clean_scope(scope, require_name=True):
            case Err() as err:
                return err
            case Ok(value=fields):
                pass
        view = repo.create(session, fields, None, engagement_id)
        for lane in lanes:
            repo.create_role(session, view.id, lane, [], False)
        audit.record(session, actor=actor_name(config),
                     action="Started this process in another country", target_type="engagement",
                     target_id=view.id, engagement_id=view.id,
                     after={**fields, "reference_engagement_id": engagement_id,
                            "from_engagement": first.name, "roles": len(lanes)})  # fmt: skip
        created = repo.get(session, view.id)
    assert created is not None
    return Ok(created)


def with_same_process(session: Session, preview: HandoffPreview) -> HandoffPreview:
    """Each pilot with the engagements of the same frame and pilot in another country."""
    others = repo.with_hand_off(session)
    pilots = []
    for pilot in preview.pilots:
        found = [
            SameProcess(engagement_id=e.id, name=e.name, country=e.country,
                        process_name=e.process_name,
                        has_published=versions_repo.latest_published(session, e.id) is not None)
            for e in others
            if e.compass is not None and e.compass.pilot_ref == pilot.ref
            and compass_service.same_frame(preview.key, pilot.cluster_ref, e.compass.key,
                                           e.compass.cluster_ref)
        ]  # fmt: skip
        pilots.append(pilot.model_copy(update={"same_process": found}))
    return preview.model_copy(update={"pilots": pilots})
