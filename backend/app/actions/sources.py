"""Source actions (PRD §4 Sources, §3.7 S0): upload, read, registry edits, delete, passages.

Uploads are stored and then read by a background job (phase P2): documents into anchored passages,
transcripts into speaker turns. Images inside PDFs become suggestions only.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.actions.redaction import NAME_ORIGINS
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import SourceKind
from app.domain.models import (
    NameReplacement,
    ParsedDocument,
    SegmentPage,
    SegmentPatch,
    SegmentView,
    SourcePatch,
    SourceReadInfo,
    SourceView,
    SpeakerView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import jobs as jobs_repo
from app.repositories import redaction as redaction_repo
from app.repositories import sources as repo
from app.services import grounding, parsing
from app.services.grounding import DEFAULT_REPLACEMENT

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

MAX_BYTES = 50 * 1024 * 1024
FORMATS = {"docx", "pdf", "txt", "vtt", "srt"}
READ_JOB = "read_source"
SOURCE_MISSING = "That source doesn't exist. It may have been deleted."
BAD_FORMAT = "Process Map Studio reads .docx, .pdf, .txt, .vtt and .srt files."
TOO_BIG = "That file is larger than 50 MB. Split it or save a smaller copy, then upload again."
EMPTY = "The file is empty."
BAD_KIND = "Please choose what kind of source this is."
BAD_DATE = "Please enter the version date as YYYY-MM-DD, or leave it blank."
BAD_OWNER = "Owner: up to 120 characters, one line."
CANT_READ_TAIL = " Check it opens on your computer, then upload it again."
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


def _parse(info: SourceReadInfo) -> Result[ParsedDocument]:
    """Read the stored file the way its format and kind call for (API_CONTRACT.md → Sources)."""
    path = Path(info.stored_path)
    transcript = info.kind == SourceKind.INTERVIEW_TRANSCRIPT.value
    if info.format == "vtt":
        return parsing.parse_vtt(path)
    if info.format == "srt":
        return parsing.parse_srt(path)
    if info.format == "txt":
        return (
            parsing.parse_transcript_text(path) if transcript else parsing.parse_text_document(path)
        )
    result = parsing.parse_docx(path) if info.format == "docx" else parsing.parse_pdf_text(path)
    match result:
        case Ok(value=document) if transcript:
            return Ok(
                document.model_copy(update={"segments": parsing.detect_speakers(document.segments)})
            )
        case _:
            return result


def _queue_read(session: Session, engagement_id: str, source_id: str) -> str:
    job = jobs_repo.create(
        session, engagement_id=engagement_id, job_type=READ_JOB, target_id=source_id
    )
    return job.id


def _public(session: Session, view: SourceView) -> SourceView:
    """The source as shown outside the owner-only places: names hidden in file name and error."""
    terms = redaction.name_replacements(session, view.engagement_id)
    return view.model_copy(
        update={
            "filename": redaction.hide(view.filename, terms),
            "error": redaction.hide(view.error, terms),
        }
    )


def upload_source(
    config: AppConfig,
    sessions: Sessions,
    engagement_id: str,
    *,
    filename: str,
    stream: BinaryIO,
    content_type: str,
    enqueue: Enqueue,
    kind: str | None = None,
    version_date: str | None = None,
    owner: str | None = None,
    controlled_copy: bool = False,
) -> Result[SourceView]:
    """Store the file and queue it to be read in the background (PRD §4: parsing runs as a job)."""
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
                "text_status": "pending",
                **meta,
            },
        )
        job_id = _queue_read(session, engagement_id, source_id)
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
        stored = repo.get(session, source_id)
        assert stored is not None
        view = _public(session, stored)
    enqueue(job_id)  # after the commit, so the worker finds the rows
    return Ok(view.model_copy(update={"job_id": job_id}))


def read_source(config: AppConfig, sessions: Sessions, source_id: str) -> Result[str]:
    """The reading job: parse the stored file into passages (PRD §3.7 S0).

    Flags instruction-like passages (G9), adds name-like speaker labels to the redaction terms
    (G10) and saves PDF images as suggestions. A file that can't be read is marked failed with a
    plain reason; its row stays so Eric can see it.
    """
    with session_scope(sessions) as session:
        info = repo.reading_info(session, source_id)
        if info is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        known_roles = engagements_repo.role_names(session, info.engagement_id)
        want_images = info.format == "pdf" and not repo.has_images(session, source_id)

    match _parse(info):
        case Err(message=message) as err:
            mark_unreadable(sessions, source_id, message + CANT_READ_TAIL)
            return Err(err.kind, message + CANT_READ_TAIL, err.details)
        case Ok(value=document):
            pass
    segments = [
        s.model_copy(update={"instruction_like": grounding.detect_instruction_like(s.text)})
        for s in document.segments
    ]
    images = parsing.extract_pdf_images(Path(info.stored_path)) if want_images else Ok([])
    names = sorted(
        {s.speaker_label for s in segments if parsing.looks_like_name(s.speaker_label, known_roles)}
    )

    with session_scope(sessions) as session:
        if repo.reading_info(session, source_id) is None:  # deleted while it was being read
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        repo.replace_segments(session, source_id, segments)
        repo.set_read_result(session, source_id, status="ready", ocr_pages=document.ocr_pages)
        for name in names:
            if redaction_repo.find(session, info.engagement_id, name, NAME_ORIGINS) is None:
                redaction_repo.add(
                    session,
                    engagement_id=info.engagement_id,
                    term=name,
                    replacement=DEFAULT_REPLACEMENT,
                    origin="speaker_map",
                )
        if isinstance(images, Ok) and images.value:
            folder = config.data_dir / "images" / info.engagement_id
            folder.mkdir(parents=True, exist_ok=True)
            for number, image in enumerate(images.value, start=1):
                path = folder / f"{source_id}-p{image.page}-{number}.{image.extension}"
                path.write_bytes(image.data)
                repo.add_suggested_image(
                    session,
                    source_id=source_id,
                    stored_path=str(path),
                    page=image.page,
                    caption=f"Image from {info.filename}, page {image.page}",
                )
    return Ok(f"Read {len(segments)} passages.")


def mark_unreadable(sessions: Sessions, source_id: str, message: str) -> None:
    with session_scope(sessions) as session:
        repo.set_read_result(session, source_id, status="failed", error=message)


def list_sources(sessions: Sessions, engagement_id: str) -> Result[list[SourceView]]:
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok([_public(session, v) for v in repo.list_for_engagement(session, engagement_id)])


def get_source(sessions: Sessions, source_id: str) -> Result[SourceView]:
    with session_scope(sessions) as session:
        view = repo.get(session, source_id)
        return Ok(_public(session, view)) if view else Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)


def _reading_changes(fmt: str, old_kind: str, new_kind: str) -> bool:
    """Whether a new kind means the file must be read again (transcript ↔ document)."""
    transcript = SourceKind.INTERVIEW_TRANSCRIPT.value
    return fmt in {"txt", "docx", "pdf"} and (old_kind == transcript) != (new_kind == transcript)


def update_source(
    config: AppConfig, sessions: Sessions, source_id: str, data: SourcePatch, enqueue: Enqueue
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
    job_id = None
    with session_scope(sessions) as session:
        before = repo.get(session, source_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        changed = {k: v for k, v in fields.items() if getattr(before, k) != v}
        if (
            "kind" in changed
            and _reading_changes(before.format, before.kind, str(changed["kind"]))
            and not repo.has_corrected_segments(session, source_id)
        ):
            fields["text_status"] = "pending"
            fields["error"] = ""
            job_id = _queue_read(session, before.engagement_id, source_id)
        updated = repo.update(session, source_id, fields)
        assert updated is not None
        view = _public(session, updated)
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
    if job_id:
        enqueue(job_id)
        return Ok(view.model_copy(update={"job_id": job_id}))
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


def _segment_view(
    fmt: str, item: dict[str, Any], terms: list[NameReplacement] | None
) -> SegmentView:
    """One passage; `terms` hides names, `None` means raw (owner-only correction editor)."""
    role = item["speaker_role"] or ("Interviewer" if item["is_interviewer"] else None)
    return SegmentView(
        id=item["id"],
        seq=item["seq"],
        anchor=parsing.segment_anchor(
            fmt=fmt,
            seq=item["seq"],
            page=item["page"],
            section=item["section"],
            text=item["text"],
            start_ms=item["start_ms"],
        ),
        page=item["page"],
        section=item["section"] if terms is None else redaction.hide(item["section"], terms),
        speaker_role=role,
        text=item["text"] if terms is None else redaction.hide(item["text"], terms),
        cited=False,
        instruction_like=item["instruction_like"],
        speaker_label=item["speaker_label"] if terms is None else None,
        corrected=item["corrected"],
    )


PASSAGE_ELSEWHERE = "That passage isn't in this source."


def list_segments(
    sessions: Sessions,
    source_id: str,
    page: int = 1,
    page_size: int = 200,
    *,
    raw: bool = False,
    around: str | None = None,
) -> Result[SegmentPage]:
    """One page of passages; with `around`, the page that holds that passage."""
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
        if around is not None:
            position = repo.segment_position(session, source_id, around)
            if position is None:
                return Err(ErrorKind.NOT_FOUND, PASSAGE_ELSEWHERE)
            page = position // page_size + 1
        items, total = repo.segment_page(session, source_id, page, page_size)
        terms = None if raw else redaction.name_replacements(session, source.engagement_id)
    segments = [_segment_view(source.format, item, terms) for item in items]
    pages = max(1, math.ceil(total / page_size))
    return Ok(
        SegmentPage(segments=segments, total=total, page=page, pages=pages, coverage_pct=None)
    )


# --- Speakers and corrections (owner-only places, PRD §3.8 G10) ------------------------------


SEGMENT_MISSING = "That passage doesn't exist."
BAD_TEXT = "Please keep the passage between 1 and 5,000 characters."
BAD_ROLE = "Choose one of this engagement's roles, or Interviewer."


def get_speakers(sessions: Sessions, source_id: str) -> Result[list[SpeakerView]]:
    with session_scope(sessions) as session:
        if repo.get(session, source_id) is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        return Ok(repo.speakers(session, source_id))


def map_speakers(
    config: AppConfig, sessions: Sessions, source_id: str, mapping: dict[str, str | None]
) -> Result[list[SpeakerView]]:
    """Map speaker labels to roles or Interviewer; name-like labels show as the mapped role."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        source = repo.get(session, source_id)
        if source is None:
            return Err(ErrorKind.NOT_FOUND, SOURCE_MISSING)
        labels = {s.label for s in repo.speakers(session, source_id)}
        roles = {r.id: r.name for r in engagements_repo.list_roles(session, source.engagement_id)}
        known = engagements_repo.role_names(session, source.engagement_id)
        for label, target in mapping.items():  # check everything before changing anything
            if label not in labels:
                return Err(
                    ErrorKind.VALIDATION,
                    f"There is no speaker called {label} in this file.",
                    {"field": "label"},
                )
            if target is not None and target != "interviewer" and target not in roles:
                return Err(ErrorKind.VALIDATION, BAD_ROLE, {"field": "role_id"})
        for label, target in mapping.items():
            interviewer = target == "interviewer"
            role_id = None if target is None or interviewer else target
            repo.map_speaker(session, source_id, label, role_id=role_id, is_interviewer=interviewer)
            if parsing.looks_like_name(label, known):
                shown = (
                    "Interviewer" if interviewer else roles.get(role_id or "", DEFAULT_REPLACEMENT)
                )
                redaction.set_speaker_term(session, source.engagement_id, label, shown)
        if mapping:
            engagements_repo.touch(session, source.engagement_id)
            audit.record(
                session,
                actor=actor,
                action="Mapped speakers",
                target_type="source",
                target_id=source_id,
                engagement_id=source.engagement_id,
                after={"speakers_mapped": sum(1 for t in mapping.values() if t is not None)},
            )
        return Ok(repo.speakers(session, source_id))


def correct_segment(
    config: AppConfig, sessions: Sessions, segment_id: str, data: SegmentPatch
) -> Result[SegmentView]:
    """The correction editor: save the passage as typed (owner-only; returned raw)."""
    text = data.text.strip()
    if not text or len(text) > 5000:
        return Err(ErrorKind.VALIDATION, BAD_TEXT, {"field": "text"})
    actor = actor_name(config)
    with session_scope(sessions) as session:
        source_id = repo.segment_source(session, segment_id)
        source = repo.get(session, source_id) if source_id else None
        if source is None:
            return Err(ErrorKind.NOT_FOUND, SEGMENT_MISSING)
        item = repo.correct_segment(
            session,
            segment_id,
            text=text,
            instruction_like=grounding.detect_instruction_like(text),
        )
        assert item is not None
        audit.record(
            session,
            actor=actor,
            action="Corrected a passage",
            target_type="segment",
            target_id=segment_id,
            engagement_id=source.engagement_id,
        )
    return Ok(_segment_view(source.format, item, None))
