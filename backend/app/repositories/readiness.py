"""Readiness facts: the stored state the guided-navigation rules read (PRD §4 readiness).

Only facts are gathered here; the rules that turn them into statuses live in
app/actions/readiness.py.
"""

from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.domain.enums import GapStatus, VersionState
from app.domain.models import ReadinessFacts, SourceFacts
from app.repositories import engagements
from app.repositories.tables import Engagement, GapAnalysis, MapVersion, Source, SourceSegment


def _unmapped_speakers(session: Session, engagement_id: str) -> dict[str, int]:
    """Per source: speaker labels that have no role yet."""
    rows = session.execute(
        select(SourceSegment.source_id, func.count(distinct(SourceSegment.speaker_label)))
        .join(Source, Source.id == SourceSegment.source_id)
        .where(Source.engagement_id == engagement_id)
        .where(SourceSegment.speaker_label != "")
        .where(SourceSegment.speaker_role_id.is_(None))
        .group_by(SourceSegment.source_id)
    )
    return {source_id: count for source_id, count in rows}


def facts(session: Session, engagement_id: str) -> ReadinessFacts | None:
    row = session.get(Engagement, engagement_id)
    if row is None:
        return None
    unmapped = _unmapped_speakers(session, engagement_id)
    sources = [
        SourceFacts(
            id=source.id,
            filename=source.filename,
            kind=source.kind,
            text_status=source.text_status,
            unmapped_speakers=unmapped.get(source.id, 0),
        )
        for source in session.scalars(
            select(Source)
            .where(Source.engagement_id == engagement_id)
            .order_by(Source.created_at, Source.id)
        )
    ]
    versions = MapVersion.engagement_id == engagement_id
    version_count = session.scalar(select(func.count()).select_from(MapVersion).where(versions))
    published = session.scalar(
        select(func.count())
        .select_from(MapVersion)
        .where(versions)
        .where(MapVersion.state.in_([VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value]))
    )
    finalised = session.scalar(
        select(func.count())
        .select_from(GapAnalysis)
        .join(MapVersion, MapVersion.id == GapAnalysis.version_id)
        .where(versions)
        .where(GapAnalysis.status == GapStatus.FINALISED.value)
    )
    _, progress = engagements.latest_version(session, engagement_id)
    return ReadinessFacts(
        trigger=row.trigger,
        end_point=row.end_point,
        sources=sources,
        version_count=version_count or 0,
        published=bool(published),
        latest_progress=progress,
        gap_finalised=bool(finalised),
    )
