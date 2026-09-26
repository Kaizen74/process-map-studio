"""Source aggregate repository: sources, their segments and their suggested images."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import ParsedSegment, SourceReadInfo, SourceView
from app.repositories.tables import Image, Role, Source, SourceSegment

EDITABLE = ("kind", "version_date", "owner", "controlled_copy", "text_status", "error")


def _counts(session: Session, source_id: str) -> tuple[int, int]:
    segments = session.scalar(
        select(func.count()).select_from(SourceSegment).where(SourceSegment.source_id == source_id)
    )
    images = session.scalar(
        select(func.count())
        .select_from(Image)
        .where(Image.source_id == source_id)
        .where(Image.status == "suggested")
    )
    return segments or 0, images or 0


def _view(session: Session, row: Source) -> SourceView:
    segment_count, suggested = _counts(session, row.id)
    return SourceView(
        id=row.id,
        engagement_id=row.engagement_id,
        kind=row.kind,
        filename=row.filename,
        format=row.format,
        mime=row.mime,
        version_date=row.version_date,
        owner=row.owner,
        controlled_copy=row.controlled_copy,
        text_status=row.text_status,
        error=row.error,
        segment_count=segment_count,
        ocr_pages=list(row.ocr_pages),
        suggested_images=suggested,
        created_at=row.created_at,
    )


def create(session: Session, source_id: str, fields: dict[str, Any]) -> SourceView:
    row = Source(id=source_id, **fields)
    session.add(row)
    session.flush()
    return _view(session, row)


def get(session: Session, source_id: str) -> SourceView | None:
    row = session.get(Source, source_id)
    return _view(session, row) if row else None


def stored_path(session: Session, source_id: str) -> str | None:
    row = session.get(Source, source_id)
    return row.stored_path if row else None


def list_for_engagement(session: Session, engagement_id: str) -> list[SourceView]:
    rows = session.scalars(
        select(Source)
        .where(Source.engagement_id == engagement_id)
        .order_by(Source.created_at, Source.id)
    )
    return [_view(session, row) for row in rows]


def update(session: Session, source_id: str, fields: dict[str, Any]) -> SourceView | None:
    row = session.get(Source, source_id)
    if row is None:
        return None
    for name, value in fields.items():
        if name in EDITABLE:
            setattr(row, name, value)
    session.flush()
    return _view(session, row)


def set_read_result(
    session: Session,
    source_id: str,
    *,
    status: str,
    error: str = "",
    ocr_pages: list[int] | None = None,
) -> None:
    """Record the outcome of reading the file."""
    row = session.get(Source, source_id)
    if row is None:
        return
    row.text_status = status
    row.error = error
    row.ocr_pages = list(ocr_pages or [])
    session.flush()


def delete(session: Session, source_id: str) -> tuple[str, list[str]] | None:
    """Delete the source and its rows. Returns its file path and its image paths (to remove)."""
    row = session.get(Source, source_id)
    if row is None:
        return None
    images = list(session.scalars(select(Image.stored_path).where(Image.source_id == source_id)))
    path = row.stored_path
    session.delete(row)
    session.flush()
    return path, images


def reading_info(session: Session, source_id: str) -> SourceReadInfo | None:
    row = session.get(Source, source_id)
    if row is None:
        return None
    return SourceReadInfo(
        id=row.id,
        engagement_id=row.engagement_id,
        filename=row.filename,
        kind=row.kind,
        format=row.format,
        stored_path=row.stored_path,
    )


def pending(session: Session) -> list[SourceReadInfo]:
    """Sources still waiting to be read, oldest first."""
    rows = session.scalars(
        select(Source).where(Source.text_status == "pending").order_by(Source.created_at, Source.id)
    )
    return [info for row in rows if (info := reading_info(session, row.id)) is not None]


def has_corrected_segments(session: Session, source_id: str) -> bool:
    return (
        session.scalar(
            select(func.count())
            .select_from(SourceSegment)
            .where(SourceSegment.source_id == source_id)
            .where(SourceSegment.corrected.is_(True))
        )
        or 0
    ) > 0


def has_images(session: Session, source_id: str) -> bool:
    count = session.scalar(
        select(func.count()).select_from(Image).where(Image.source_id == source_id)
    )
    return (count or 0) > 0


def replace_segments(session: Session, source_id: str, segments: list[ParsedSegment]) -> None:
    """Store a fresh reading of the file. Speaker mappings are kept by label."""
    mapping: dict[str, tuple[str | None, bool]] = {}
    for old in session.scalars(select(SourceSegment).where(SourceSegment.source_id == source_id)):
        if old.speaker_label and (old.speaker_role_id or old.is_interviewer):
            mapping[old.speaker_label] = (old.speaker_role_id, old.is_interviewer)
        session.delete(old)
    session.flush()
    for segment in segments:
        role_id, is_interviewer = mapping.get(segment.speaker_label, (None, False))
        session.add(
            SourceSegment(
                source_id=source_id,
                seq=segment.seq,
                speaker_label=segment.speaker_label,
                speaker_role_id=role_id,
                is_interviewer=is_interviewer,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                page=segment.page,
                section=segment.section,
                text=segment.text,
                instruction_like=segment.instruction_like,
            )
        )
    session.flush()


def segment_page(
    session: Session, source_id: str, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    """One page of segments in reading order, with the mapped role name (if any)."""
    total = (
        session.scalar(
            select(func.count())
            .select_from(SourceSegment)
            .where(SourceSegment.source_id == source_id)
        )
        or 0
    )
    rows = session.execute(
        select(SourceSegment, Role.name)
        .outerjoin(Role, Role.id == SourceSegment.speaker_role_id)
        .where(SourceSegment.source_id == source_id)
        .order_by(SourceSegment.seq)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": seg.id,
            "seq": seg.seq,
            "page": seg.page,
            "section": seg.section,
            "start_ms": seg.start_ms,
            "speaker_role": role_name,
            "text": seg.text,
            "instruction_like": seg.instruction_like,
        }
        for seg, role_name in rows
    ]
    return items, total


def add_suggested_image(
    session: Session, *, source_id: str, stored_path: str, page: int, caption: str
) -> None:
    session.add(
        Image(
            source_id=source_id,
            stored_path=stored_path,
            page=page,
            caption=caption,
            origin="extracted",
            status="suggested",
        )
    )
    session.flush()
