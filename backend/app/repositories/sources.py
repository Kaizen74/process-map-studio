"""Source aggregate repository: sources, their segments and their suggested images."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import (
    ParsedSegment,
    SourceReadInfo,
    SourceView,
    SpeakerView,
    StoredSegment,
)
from app.repositories.read_memo import remembered
from app.repositories.tables import Image, Role, Source, SourceSegment, new_id

EDITABLE = ("kind", "version_date", "owner", "controlled_copy", "text_status", "error")


# The pictures found in a file: its own, not the copies a draft suggests on a step (2026-10-29:
# Sources said "4 images found in this file" for a file with two, after a draft).
_FOUND_IN_FILE = (
    Image.element_id.is_(None),
    Image.origin == "extracted",
    Image.status == "suggested",
)


def _counts(session: Session, source_id: str) -> tuple[int, int]:
    segments = session.scalar(
        select(func.count()).select_from(SourceSegment).where(SourceSegment.source_id == source_id)
    )
    images = session.scalar(
        select(func.count()).select_from(Image).where(Image.source_id == source_id, *_FOUND_IN_FILE)
    )
    return segments or 0, images or 0


def _view(session: Session, row: Source, counts: tuple[int, int] | None = None) -> SourceView:
    segment_count, suggested = counts if counts is not None else _counts(session, row.id)
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


@remembered
def get_many(session: Session, source_ids: list[str]) -> list[SourceView]:
    """The sources with these IDs, in the order given (missing ones left out); three queries in
    all, however many sources (the quality card and graph read every source of a version)."""
    if not source_ids:
        return []
    rows = {r.id: r for r in session.scalars(select(Source).where(Source.id.in_(source_ids)))}
    segments: dict[str, int] = {
        str(sid): n
        for sid, n in session.execute(
            select(SourceSegment.source_id, func.count())
            .where(SourceSegment.source_id.in_(source_ids))
            .group_by(SourceSegment.source_id)
        )
    }
    images: dict[str, int] = {
        str(sid): n
        for sid, n in session.execute(
            select(Image.source_id, func.count())
            .where(Image.source_id.in_(source_ids), *_FOUND_IN_FILE)
            .group_by(Image.source_id)
        )
    }
    return [
        _view(session, rows[sid], (segments.get(sid, 0), images.get(sid, 0)))
        for sid in source_ids
        if sid in rows
    ]


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
    session: Session,
    source_id: str,
    page: int,
    page_size: int,
    *,
    uncited_besides: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """One page of segments in reading order, with the mapped role name (if any). With
    `uncited_besides`, only the passages not in that set, interviewer turns left out (G11)."""
    where = [SourceSegment.source_id == source_id]
    if uncited_besides is not None:
        where += [
            SourceSegment.id.not_in(uncited_besides),
            SourceSegment.is_interviewer.is_(False),
        ]
    total = session.scalar(select(func.count()).select_from(SourceSegment).where(*where)) or 0
    rows = session.execute(
        select(SourceSegment, Role.name)
        .outerjoin(Role, Role.id == SourceSegment.speaker_role_id)
        .where(*where)
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
            "speaker_label": seg.speaker_label,
            "is_interviewer": seg.is_interviewer,
            "text": seg.text,
            "instruction_like": seg.instruction_like,
            "corrected": seg.corrected,
            "question_id": seg.question_id,
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


def speakers(session: Session, source_id: str) -> list[SpeakerView]:
    """Each speaker label in order of first appearance, with how its passages are mapped."""
    found: dict[str, SpeakerView] = {}
    rows = session.scalars(
        select(SourceSegment)
        .where(SourceSegment.source_id == source_id)
        .where(SourceSegment.speaker_label != "")
        .order_by(SourceSegment.seq)
    )
    for row in rows:
        entry = found.get(row.speaker_label)
        if entry is None:
            found[row.speaker_label] = SpeakerView(
                label=row.speaker_label,
                segment_count=1,
                role_id=row.speaker_role_id,
                is_interviewer=row.is_interviewer,
            )
        else:
            entry.segment_count += 1
    return list(found.values())


def map_speaker(
    session: Session, source_id: str, label: str, *, role_id: str | None, is_interviewer: bool
) -> None:
    rows = session.scalars(
        select(SourceSegment)
        .where(SourceSegment.source_id == source_id)
        .where(SourceSegment.speaker_label == label)
    )
    for row in rows:
        row.speaker_role_id = role_id
        row.is_interviewer = is_interviewer
    session.flush()


def segment_source(session: Session, segment_id: str) -> str | None:
    """The source a passage belongs to (None if the passage doesn't exist)."""
    row = session.get(SourceSegment, segment_id)
    return row.source_id if row else None


def segment_position(session: Session, source_id: str, segment_id: str) -> int | None:
    """How many passages of the source come before this one in reading order (None if the
    passage isn't in this source)."""
    row = session.get(SourceSegment, segment_id)
    if row is None or row.source_id != source_id:
        return None
    return (
        session.scalar(
            select(func.count())
            .select_from(SourceSegment)
            .where(SourceSegment.source_id == source_id, SourceSegment.seq < row.seq)
        )
        or 0
    )


def correct_segment(
    session: Session, segment_id: str, *, text: str, instruction_like: bool
) -> dict[str, Any] | None:
    """Save Eric's correction; returns the passage as stored (with its role name)."""
    row = session.get(SourceSegment, segment_id)
    if row is None:
        return None
    row.text = text
    row.corrected = True
    row.instruction_like = instruction_like
    session.flush()
    role = session.get(Role, row.speaker_role_id) if row.speaker_role_id else None
    return {
        "id": row.id,
        "seq": row.seq,
        "page": row.page,
        "section": row.section,
        "start_ms": row.start_ms,
        "speaker_role": role.name if role else None,
        "speaker_label": row.speaker_label,
        "is_interviewer": row.is_interviewer,
        "text": row.text,
        "instruction_like": row.instruction_like,
        "corrected": row.corrected,
        "question_id": row.question_id,
    }


def stored_segments(session: Session, source_id: str) -> list[StoredSegment]:
    """Every passage of a source in reading order, with its speaker's role name."""
    rows = session.execute(
        select(SourceSegment, Role.name)
        .outerjoin(Role, Role.id == SourceSegment.speaker_role_id)
        .where(SourceSegment.source_id == source_id)
        .order_by(SourceSegment.seq)
    )
    return [
        StoredSegment(
            id=seg.id,
            seq=seg.seq,
            page=seg.page,
            section=seg.section,
            start_ms=seg.start_ms,
            text=seg.text,
            speaker_label=seg.speaker_label,
            speaker_role=role_name,
            is_interviewer=seg.is_interviewer,
            instruction_like=seg.instruction_like,
        )
        for seg, role_name in rows
    ]


def set_question_ids(session: Session, source_id: str, by_seq: dict[int, str | None]) -> None:
    """Step A (§3.12.10): the guide question each turn asks or answers."""
    for seg in session.scalars(select(SourceSegment).where(SourceSegment.source_id == source_id)):
        seg.question_id = by_seq.get(seg.seq)
    session.flush()


def ocr_pages(session: Session, source_id: str) -> list[int]:
    row = session.get(Source, source_id)
    return list(row.ocr_pages) if row else []


def add_page_text(
    session: Session, source_id: str, page: int, lines: list[tuple[str, bool]]
) -> None:
    """Store the text read from a scanned page (lines with their instruction-like flag), put the
    passages in page order and take the page off the list waiting to be read."""
    row = session.get(Source, source_id)
    if row is None:
        return
    for index, (text, instruction_like) in enumerate(lines):
        session.add(
            SourceSegment(
                source_id=source_id,
                seq=10**6 + index,  # after every existing passage; renumbered below
                page=page,
                text=text,
                instruction_like=instruction_like,
            )
        )
    session.flush()
    ordered = session.scalars(
        select(SourceSegment).where(SourceSegment.source_id == source_id)
    ).all()
    ordered = sorted(ordered, key=lambda s: (s.page if s.page is not None else 0, s.seq))
    for number, segment in enumerate(ordered, start=1):
        segment.seq = number
    row.ocr_pages = [p for p in row.ocr_pages if p != page]
    session.flush()


def segment_rows(session: Session, segment_ids: list[str]) -> dict[str, tuple[SourceSegment, str]]:
    """Passages by ID with their source's format (to build anchors); missing IDs are left out."""
    if not segment_ids:
        return {}
    rows = session.execute(
        select(SourceSegment, Source.format)
        .join(Source, Source.id == SourceSegment.source_id)
        .where(SourceSegment.id.in_(segment_ids))
    )
    return {seg.id: (seg, fmt) for seg, fmt in rows}


def segment_owners(session: Session, segment_ids: list[str]) -> dict[str, tuple[str, str, str]]:
    """Passage ID → (source ID, engagement ID, source kind); missing IDs are left out."""
    if not segment_ids:
        return {}
    rows = session.execute(
        select(SourceSegment.id, Source.id, Source.engagement_id, Source.kind)
        .join(Source, Source.id == SourceSegment.source_id)
        .where(SourceSegment.id.in_(segment_ids))
    )
    return {seg: (src, eng, kind) for seg, src, eng, kind in rows}


def instruction_like_count(session: Session, engagement_id: str) -> int:
    """Passages in an engagement's sources that looked like instructions (treated as data, G9)."""
    return (
        session.scalar(
            select(func.count())
            .select_from(SourceSegment)
            .join(Source, Source.id == SourceSegment.source_id)
            .where(Source.engagement_id == engagement_id, SourceSegment.instruction_like.is_(True))
        )
        or 0
    )


@remembered
def speaker_roles(session: Session, segment_ids: list[str]) -> dict[str, str]:
    """Passage ID → the role its speaker is mapped to (passages without a mapped speaker are
    left out)."""
    if not segment_ids:
        return {}
    rows = session.execute(
        select(SourceSegment.id, Role.name)
        .join(Role, Role.id == SourceSegment.speaker_role_id)
        .where(SourceSegment.id.in_(segment_ids))
    )
    return {segment_id: name for segment_id, name in rows}


def coverage_counts(
    session: Session, source_ids: list[str], cited: set[str]
) -> dict[str, tuple[int, int]]:
    """For each source: (cited passages, passages), interviewer turns left out (G11)."""
    counts = {sid: (0, 0) for sid in source_ids}
    rows = session.execute(
        select(SourceSegment.id, SourceSegment.source_id).where(
            SourceSegment.source_id.in_(source_ids), SourceSegment.is_interviewer.is_(False)
        )
    )
    for segment_id, source_id in rows:
        hit, total = counts[source_id]
        counts[source_id] = (hit + (segment_id in cited), total + 1)
    return counts


def question_ids(session: Session, source_id: str) -> set[str]:
    """The guide questions (Appendix F IDs) the source's passages answer."""
    rows = session.scalars(
        select(SourceSegment.question_id).where(
            SourceSegment.source_id == source_id, SourceSegment.question_id.is_not(None)
        )
    )
    return {q for q in rows if q}


def kinds(session: Session, engagement_id: str) -> list[tuple[str, str, str]]:
    """(ID, kind, text status) of each of the engagement's sources, without counting passages."""
    rows = session.execute(
        select(Source.id, Source.kind, Source.text_status)
        .where(Source.engagement_id == engagement_id)
        .order_by(Source.created_at, Source.id)
    )
    return [(i, k, t) for i, k, t in rows]


def text_characters(session: Session, source_ids: list[str]) -> int:
    """The characters of the sources' passages (for the draft cost estimate)."""
    if not source_ids:
        return 0
    total = session.scalar(
        select(func.coalesce(func.sum(func.length(SourceSegment.text)), 0)).where(
            SourceSegment.source_id.in_(source_ids)
        )
    )
    return int(total or 0)


@dataclass(frozen=True, slots=True)
class CopiedSource:
    old_path: str
    new_id: str
    format: str
    pictures: list[tuple[str, int, str]]  # (stored path, page, caption) of the source's own


def copy_source(
    session: Session, source_id: str, copy: tuple[str, str, str], roles: dict[str, str]
) -> CopiedSource | None:
    """Another flow from the same sources (DECISIONS 81): the source row and every passage as
    read (corrections and speaker mappings included, roles mapped to the new engagement's), so
    nothing is read or sent again. The file and pictures are copied by the caller."""
    row = session.get(Source, source_id)
    if row is None:
        return None
    copy_id, engagement_id, new_path = copy  # the copy's ID, engagement and stored file
    new = Source(
        id=copy_id,
        engagement_id=engagement_id,
        kind=row.kind,
        filename=row.filename,
        stored_path=new_path,
        mime=row.mime,
        format=row.format,
        version_date=row.version_date,
        owner=row.owner,
        controlled_copy=row.controlled_copy,
        text_status=row.text_status,
        error=row.error,
        ocr_pages=list(row.ocr_pages),
    )
    session.add(new)
    session.flush()
    segments = list(
        session.scalars(
            select(SourceSegment)
            .where(SourceSegment.source_id == source_id)
            .order_by(SourceSegment.seq)
        )
    )
    copies = {s.id: new_id() for s in segments}
    for s in segments:
        session.add(
            SourceSegment(
                id=copies[s.id],
                source_id=new.id,
                seq=s.seq,
                speaker_label=s.speaker_label,
                speaker_role_id=roles.get(s.speaker_role_id or ""),
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                page=s.page,
                section=s.section,
                text=s.text,
                corrected=s.corrected,
                instruction_like=s.instruction_like,
                is_interviewer=s.is_interviewer,
                question_id=s.question_id,
                answer_block_id=(
                    copies.get(s.answer_block_id, s.answer_block_id) if s.answer_block_id else None
                ),
                marker_tags=s.marker_tags,
            )
        )
    session.flush()
    pictures = [
        (img.stored_path, img.page or 0, img.caption)
        for img in session.scalars(
            select(Image)
            .where(
                Image.source_id == source_id,
                Image.element_id.is_(None),
                Image.origin == "extracted",
            )
            .order_by(Image.created_at, Image.id)
        )
    ]
    return CopiedSource(
        old_path=row.stored_path, new_id=new.id, format=row.format, pictures=pictures
    )


def files_for_engagement(session: Session, engagement_id: str) -> list[tuple[str, str, str, str]]:
    """(source ID, format, file name, reading status) of every source of an engagement, oldest
    first."""
    rows = session.execute(
        select(Source.id, Source.format, Source.filename, Source.text_status)
        .where(Source.engagement_id == engagement_id)
        .order_by(Source.created_at, Source.id)
    )
    return [(sid, fmt, name, status) for sid, fmt, name, status in rows]
