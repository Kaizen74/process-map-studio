"""Source actions (PRD §4 Sources, §3.7 S0): upload, read, registry edits, delete, passages.

Word and PDF files are read on upload (phase P1). Transcript formats (.txt, .vtt, .srt) are
stored and read from phase P2. Images inside PDFs become suggestions only.
"""

from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session, sessionmaker

from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import SourceKind
from app.domain.models import ParsedDocument, SegmentPage, SegmentView, SourcePatch, SourceView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import sources as repo
from app.services import parsing

Sessions = sessionmaker[Session]

MAX_BYTES = 50 * 1024 * 1024
FORMATS = {"docx", "pdf", "txt", "vtt", "srt"}
READ_NOW = {"docx", "pdf"}
SOURCE_MISSING = "That source doesn't exist. It may have been deleted."
BAD_FORMAT = "Process Map Studio reads .docx, .pdf, .txt, .vtt and .srt files."
TOO_BIG = "That file is larger than 50 MB. Split it or save a smaller copy, then upload again."
EMPTY = "The file is empty."
BAD_KIND = "Please choose what kind of source this is."
BAD_DATE = "Please enter the version date as YYYY-MM-DD, or leave it blank."
BAD_OWNER = "Owner: up to 120 characters, one line."
PENDING_P2 = "Waiting: transcript files are read from build phase P2."
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def guess_kind(filename: str) -> SourceKind:
    """A sensible default kind from the file name; Eric can change it in the registry."""
    name = filename.lower()
    if name.endswith((".vtt", ".srt")) or "transcript" in name or "interview" in name:
        return SourceKind.INTERVIEW_TRANSCRIPT
    if (
        re.search(r"(^|[^a-z])jd([^a-z]|$)", name)
        or "job description" in name
        or "job_description" in name
    ):
        return SourceKind.JOB_DESCRIPTION
    if "sop" in name:
        return SourceKind.SOP
    if "manual" in name:
        return SourceKind.MANUAL
    return SourceKind.OTHER


def _check_meta(
    kind: str | None, version_date: str | None, owner: str | None
) -> Result[dict[str, object]]:
    fields: dict[str, object] = {}
    if kind is not None:
        if kind not in {k.value for k in SourceKind}:
            return Err(ErrorKind.VALIDATION, BAD_KIND, {"field": "kind"})
        fields["kind"] = kind
    if version_date is not None:
        date = version_date.strip()
        if date and not _DATE.match(date):
            return Err(ErrorKind.VALIDATION, BAD_DATE, {"field": "version_date"})
        fields["version_date"] = date
    if owner is not None:
        text = owner.strip()
        if len(text) > 120 or "\n" in text:
            return Err(ErrorKind.VALIDATION, BAD_OWNER, {"field": "owner"})
        fields["owner"] = text
    return Ok(fields)


def _save_upload(stream: BinaryIO, target: Path) -> Result[int]:
    """Copy the upload to disk in chunks, stopping at the size limit."""
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with target.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_BYTES:
                    out.close()
                    target.unlink(missing_ok=True)
                    return Err(ErrorKind.VALIDATION, TOO_BIG, {"field": "file"})
                out.write(chunk)
    except OSError as exc:
        target.unlink(missing_ok=True)
        return Err(
            ErrorKind.IO,
            "The file couldn't be saved in the app's data folder.",
            {"reason": type(exc).__name__},
        )
    if written == 0:
        target.unlink(missing_ok=True)
        return Err(ErrorKind.VALIDATION, EMPTY, {"field": "file"})
    return Ok(written)


def _read(fmt: str, path: Path) -> Result[ParsedDocument]:
    return parsing.parse_docx(path) if fmt == "docx" else parsing.parse_pdf_text(path)


def upload_source(
    config: AppConfig,
    sessions: Sessions,
    engagement_id: str,
    *,
    filename: str,
    stream: BinaryIO,
    content_type: str,
    kind: str | None = None,
    version_date: str | None = None,
    owner: str | None = None,
    controlled_copy: bool = False,
) -> Result[SourceView]:
    display_name = Path(filename or "").name.strip() or "unnamed"
    fmt = Path(display_name).suffix.lower().lstrip(".")
    if fmt not in FORMATS:
        return Err(ErrorKind.VALIDATION, BAD_FORMAT, {"field": "file"})
    match _check_meta(kind or guess_kind(display_name).value, version_date, owner):
        case Err() as err:
            return err
        case Ok(value=meta):
            pass
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)

    source_id = str(uuid.uuid4())
    target = config.data_dir / "sources" / engagement_id / f"{source_id}.{fmt}"
    match _save_upload(stream, target):
        case Err() as err:
            return err
        case Ok():
            pass

    # Read the text before opening the unit of work (reading can take a few seconds).
    document: ParsedDocument | None = None
    read_error = ""
    if fmt in READ_NOW:
        match _read(fmt, target):
            case Ok(value=parsed):
                document = parsed
            case Err(message=message):
                read_error = f"{message} Check it opens on your computer, then upload it again."
    images = parsing.extract_pdf_images(target) if fmt == "pdf" and document else Ok([])

    actor = actor_name(config)
    with session_scope(sessions) as session:
        repo.create(
            session,
            source_id,
            {
                "engagement_id": engagement_id,
                "filename": display_name,
                "stored_path": str(target),
                "mime": content_type or "",
                "format": fmt,
                "controlled_copy": controlled_copy,
                **meta,
            },
        )
        if document is not None:
            repo.add_segments(session, source_id, document.segments)
            repo.set_read_result(session, source_id, status="ready", ocr_pages=document.ocr_pages)
        elif read_error:
            repo.set_read_result(session, source_id, status="failed", error=read_error)
        else:
            repo.set_read_result(session, source_id, status="pending", error=PENDING_P2)
        if isinstance(images, Ok):
            folder = config.data_dir / "images" / engagement_id
            folder.mkdir(parents=True, exist_ok=True)
            for number, image in enumerate(images.value, start=1):
                path = folder / f"{source_id}-p{image.page}-{number}.{image.extension}"
                path.write_bytes(image.data)
                repo.add_suggested_image(
                    session,
                    source_id=source_id,
                    stored_path=str(path),
                    page=image.page,
                    caption=f"Image from {display_name}, page {image.page}",
                )
        engagements_repo.touch(session, engagement_id)
        audit.record(
            session,
            actor=actor,
            action="Added source",
            target_type="source",
            target_id=source_id,
            engagement_id=engagement_id,
            after={"filename": display_name, "kind": meta["kind"]},
        )
        view = repo.get(session, source_id)
    assert view is not None
    return Ok(view)


def list_sources(sessions: Sessions, engagement_id: str) -> Result[list[SourceView]]:
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(repo.list_for_engagement(session, engagement_id))


def get_source(sessions: Sessions, source_id: str) -> Result[SourceView]:
    with session_scope(sessions) as session:
        view = repo.get(session, source_id)
    return Ok(view) if view else Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)


def update_source(
    config: AppConfig, sessions: Sessions, source_id: str, data: SourcePatch
) -> Result[SourceView]:
    sent = data.model_dump(exclude_unset=True)
    match _check_meta(sent.get("kind"), sent.get("version_date"), sent.get("owner")):
        case Err() as err:
            return err
        case Ok(value=fields):
            pass
    if sent.get("controlled_copy") is not None:
        fields["controlled_copy"] = bool(sent["controlled_copy"])
    actor = actor_name(config)
    with session_scope(sessions) as session:
        before = repo.get(session, source_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        view = repo.update(session, source_id, fields)
        assert view is not None
        changed = {k: v for k, v in fields.items() if getattr(before, k) != v}
        if changed:
            engagements_repo.touch(session, before.engagement_id)
            audit.record(
                session,
                actor=actor,
                action="Edited source details",
                target_type="source",
                target_id=source_id,
                engagement_id=before.engagement_id,
                before={k: getattr(before, k) for k in changed},
                after=changed,
            )
    return Ok(view)


def delete_source(config: AppConfig, sessions: Sessions, source_id: str) -> Result[None]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        before = repo.get(session, source_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        removed = repo.delete(session, source_id)
        assert removed is not None
        engagements_repo.touch(session, before.engagement_id)
        audit.record(
            session,
            actor=actor,
            action="Deleted source",
            target_type="source",
            target_id=source_id,
            engagement_id=before.engagement_id,
            before={"filename": before.filename, "kind": before.kind},
        )
    file_path, image_paths = removed
    data_root = config.data_dir.resolve()
    for name in (file_path, *image_paths):
        path = Path(name).resolve()
        if path.is_relative_to(data_root):  # never delete anything outside the data folder
            path.unlink(missing_ok=True)
    return Ok(None)


def list_segments(
    sessions: Sessions, source_id: str, page: int = 1, page_size: int = 200
) -> Result[SegmentPage]:
    if page < 1 or not 1 <= page_size <= 500:
        return Err(
            ErrorKind.VALIDATION,
            "Page must be 1 or more, and page size 1 to 500.",
            {"field": "page"},
        )
    with session_scope(sessions) as session:
        source = repo.get(session, source_id)
        if source is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        items, total = repo.segment_page(session, source_id, page, page_size)
    segments = [
        SegmentView(
            id=item["id"],
            seq=item["seq"],
            anchor=parsing.segment_anchor(
                fmt=source.format,
                seq=item["seq"],
                page=item["page"],
                section=item["section"],
                text=item["text"],
                start_ms=item["start_ms"],
            ),
            page=item["page"],
            section=item["section"],
            speaker_role=item["speaker_role"],
            text=item["text"],
            cited=False,
            instruction_like=item["instruction_like"],
        )
        for item in items
    ]
    pages = max(1, math.ceil(total / page_size))
    return Ok(
        SegmentPage(segments=segments, total=total, page=page, pages=pages, coverage_pct=None)
    )
