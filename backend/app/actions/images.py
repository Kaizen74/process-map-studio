"""Pictures on steps (PRD §4 Images, §5.7.7 item 10, constraint 11; phase P8).

An upload is checked, stripped of every piece of metadata and stored with a thumbnail under the
data folder; the original bytes are never written. Every image needs a caption (no hidden names),
a type and the redaction confirmation, whether uploaded or kept from a PDF suggestion. Images
change on a draft only and never appear in an export.
"""

from __future__ import annotations

import uuid
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.review import DRAFT_STATE, NOT_A_DRAFT
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, ImageStatus, ImageType
from app.domain.models import ImagePatch, ImageRecord, ImageView, NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import images as repo
from app.repositories import versions as versions_repo
from app.services import grounding
from app.services import images as pictures

Sessions = sessionmaker[Session]

IMAGE_MISSING = "That image doesn't exist."
STEP_MISSING = "That step doesn't exist."
NOT_A_STEP = "Pictures go on steps; the start and end come from Setup."
CAPTION = "Add a caption of up to 300 characters."
HIDDEN_NAME = "The caption contains a name from your list of names to hide. Use the role instead."
IMAGE_TYPE = "Choose what kind of picture this is."
CONFIRM = (
    "Confirm that faces, names, badge numbers and flight identifiers are removed or not shown."
)
NOT_SUGGESTED = "Only a suggested picture can be kept or discarded."
DISCARD_INSTEAD = "Discard a suggested picture instead of removing it."
TYPES = {t.value for t in ImageType}
STRUCTURAL = {ElementKind.START.value, ElementKind.END.value}


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _view(session: Session, image: ImageRecord, engagement_id: str) -> ImageView:
    return _views(session, [image], engagement_id)[0]


def _views(session: Session, found: list[ImageRecord], engagement_id: str) -> list[ImageView]:
    terms = redaction.name_replacements(session, engagement_id)
    names = repo.source_names(session, sorted({i.source_id for i in found if i.source_id}))
    return [_one_view(image, terms, names) for image in found]


def _one_view(image: ImageRecord, terms: list[NameReplacement], names: dict[str, str]) -> ImageView:
    return ImageView(
        id=image.id,
        element_id=image.element_id,
        caption=redaction.hide(image.caption, terms),
        image_type=image.image_type,
        origin=image.origin,
        status=image.status,
        redaction_confirmed=image.redaction_confirmed,
        source_name=redaction.hide(names.get(image.source_id or "", ""), terms),
        page=image.page,
        created_at=image.created_at,
    )


def _check_fields(
    session: Session, engagement_id: str, caption: str, image_type: str | None, confirmed: bool
) -> Result[str]:
    """The caption, type and confirmation every image needs; the tidy caption."""
    text = " ".join(caption.split())
    if not 1 <= len(text) <= 300:
        return _invalid("caption", CAPTION)
    terms = [t.term for t in redaction.name_replacements(session, engagement_id)]
    if grounding.scan_redaction_terms(text, terms):
        return _invalid("caption", HIDDEN_NAME)
    if image_type not in TYPES:
        return _invalid("image_type", IMAGE_TYPE)
    if not confirmed:
        return _invalid("redaction_confirmed", CONFIRM)
    return Ok(text)


def _step(session: Session, element_id: str) -> Result[tuple[str, str]]:
    """(version_id, engagement_id) of a step on a draft."""
    found = repo.owner(session, element_id)
    if found is None:
        return Err(ErrorKind.NOT_FOUND, STEP_MISSING)
    version_id, state, engagement_id = found
    element = map_repo.element(session, element_id)
    assert element is not None
    if state != DRAFT_STATE:
        return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
    if element.kind in STRUCTURAL:
        return _invalid("element", NOT_A_STEP)
    return Ok((version_id, engagement_id))


def upload(
    config: AppConfig,
    sessions: Sessions,
    element_id: str,
    *,
    stream: BinaryIO,
    caption: str,
    image_type: str | None,
    redaction_confirmed: bool,
) -> Result[ImageView]:
    data = stream.read(pictures.MAX_BYTES + 1)
    if not data:
        return _invalid("file", pictures.WRONG_TYPE)
    with session_scope(sessions) as session:
        match _step(session, element_id):
            case Err() as err:
                return err
            case Ok(value=(version_id, engagement_id)):
                pass
        match _check_fields(session, engagement_id, caption, image_type, redaction_confirmed):
            case Err() as err:
                return err
            case Ok(value=text):
                pass
    match pictures.validate_image(data):
        case Err() as err:
            return err
        case Ok(value=facts):
            pass
    match pictures.strip_metadata(data):
        case Err() as err:
            return err
        case Ok(value=clean):
            pass
    match pictures.make_thumbnail(clean):
        case Err() as err:
            return err
        case Ok(value=thumb):
            pass
    target = config.data_dir / "images" / engagement_id / f"{uuid.uuid4()}.{facts.extension}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(clean)
        pictures.thumb_path(str(target)).write_bytes(thumb)
    except OSError as exc:
        return Err(ErrorKind.IO, "The picture couldn't be saved in the app's data folder.",
                   {"reason": type(exc).__name__})  # fmt: skip
    actor = actor_name(config)
    with session_scope(sessions) as session:
        image = repo.add(
            session,
            ImageRecord(
                element_id=element_id,
                stored_path=str(target),
                caption=text,
                image_type=image_type,
                origin="uploaded",
                status=ImageStatus.KEPT.value,
                redaction_confirmed=True,
            ),
        )
        audit.record(session, actor=actor, action="Added image", target_type="element",
                     target_id=element_id, engagement_id=engagement_id, version_id=version_id,
                     after={"image_type": image_type})  # fmt: skip
        return Ok(_view(session, image, engagement_id))


def list_images(sessions: Sessions, element_id: str) -> Result[list[ImageView]]:
    with session_scope(sessions) as session:
        found = repo.owner(session, element_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, STEP_MISSING)
        return Ok(_views(session, repo.for_element(session, element_id), found[2]))


def _image_on_draft(session: Session, image_id: str) -> Result[tuple[ImageRecord, str, str]]:
    image = repo.get(session, image_id)
    if image is None or image.element_id is None:
        return Err(ErrorKind.NOT_FOUND, IMAGE_MISSING)
    found = repo.owner(session, image.element_id)
    assert found is not None
    version_id, state, engagement_id = found
    if state != DRAFT_STATE:
        return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
    return Ok((image, version_id, engagement_id))


def change(
    config: AppConfig, sessions: Sessions, image_id: str, patch: ImagePatch
) -> Result[ImageView]:
    """Keep or discard a suggestion (keeping needs caption, type and confirmation), or change
    the caption or type of any image."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        match _image_on_draft(session, image_id):
            case Err() as err:
                return err
            case Ok(value=(image, version_id, engagement_id)):
                pass
        caption = patch.caption if patch.caption is not None else image.caption
        image_type = patch.image_type if patch.image_type is not None else image.image_type
        fields: dict[str, object] = {}
        if patch.status is not None and patch.status != image.status:
            allowed = (ImageStatus.KEPT.value, ImageStatus.DISCARDED.value)
            if image.status != ImageStatus.SUGGESTED.value or patch.status not in allowed:
                return _invalid("status", NOT_SUGGESTED)
            fields["status"] = patch.status
            if patch.status == ImageStatus.KEPT.value:
                confirmed = bool(patch.redaction_confirmed)
                match _check_fields(session, engagement_id, caption, image_type, confirmed):
                    case Err() as err:
                        return err
                    case Ok(value=text):
                        fields.update(caption=text, image_type=image_type, redaction_confirmed=True)
            action = (
                "Kept suggested image" if patch.status == "kept" else "Discarded suggested image"
            )
        elif patch.caption is not None or patch.image_type is not None:
            match _check_fields(session, engagement_id, caption, image_type, True):
                case Err() as err:
                    return err
                case Ok(value=text):
                    fields.update(caption=text, image_type=image_type)
            action = "Changed image caption"
        if not fields:
            return Ok(_view(session, image, engagement_id))
        updated = repo.update(session, image_id, fields)
        audit.record(
            session,
            actor=actor,
            action=action,
            target_type="element",
            target_id=image.element_id or "",
            engagement_id=engagement_id,
            version_id=version_id,
            before={"status": image.status},
            after={"status": updated.status},
        )
        return Ok(_view(session, updated, engagement_id))


def remove(config: AppConfig, sessions: Sessions, image_id: str) -> Result[None]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        match _image_on_draft(session, image_id):
            case Err() as err:
                return err
            case Ok(value=(image, version_id, engagement_id)):
                pass
        if image.origin != "uploaded":
            return _invalid("status", DISCARD_INSTEAD)
        repo.delete(session, image_id)
        last = repo.path_users(session, image.stored_path) == 0
        audit.record(session, actor=actor, action="Removed image", target_type="element",
                     target_id=image.element_id or "", engagement_id=engagement_id,
                     version_id=version_id)  # fmt: skip
    if last:
        Path(image.stored_path).unlink(missing_ok=True)
        pictures.thumb_path(image.stored_path).unlink(missing_ok=True)
    return Ok(None)


def image_file(sessions: Sessions, image_id: str, thumb: bool) -> Result[tuple[bytes, str]]:
    """The stored picture (or its thumbnail, made once if missing) and its media type."""
    with session_scope(sessions) as session:
        image = repo.get(session, image_id)
    if image is None:
        return Err(ErrorKind.NOT_FOUND, IMAGE_MISSING)
    path = Path(image.stored_path)
    try:
        data = path.read_bytes()
    except OSError:
        return Err(ErrorKind.NOT_FOUND, IMAGE_MISSING)
    match pictures.picture_facts(data):
        case Err():
            return Err(ErrorKind.NOT_FOUND, IMAGE_MISSING)
        case Ok(value=facts):
            pass
    if not thumb:
        return Ok((data, facts.media_type))
    small = pictures.thumb_path(image.stored_path)
    if small.exists():
        return Ok((small.read_bytes(), facts.media_type))
    match pictures.make_thumbnail(data):
        case Err():
            return Ok((data, facts.media_type))
        case Ok(value=made):
            with suppress(OSError):  # a thumbnail that can't be saved is simply made again
                small.write_bytes(made)
            return Ok((made, facts.media_type))


# --- Suggestions from PDFs and the version's pictures (P8 increment 2) ---------------------------


def _ensure_clean(stored_path: str) -> bool:
    """A PDF picture saved before P8 was stored as found: re-encode it without metadata the first
    time it is suggested (a saved thumbnail marks a clean file). False if it can't be opened."""
    small = pictures.thumb_path(stored_path)
    if small.exists():
        return True
    try:
        data = Path(stored_path).read_bytes()
    except OSError:
        return False
    match pictures.clean_extracted(data):
        case Err():
            return False
        case Ok(value=(clean, _facts)):
            pass
    match pictures.make_thumbnail(clean):
        case Err():
            return False
        case Ok(value=thumb):
            pass
    try:
        Path(stored_path).write_bytes(clean)
        small.write_bytes(thumb)
    except OSError:
        return False
    return True


def attach_suggestions(session: Session, version_id: str) -> int:
    """Suggest each PDF picture on the steps whose verified evidence cites its page (API_CONTRACT
    → Suggested images from PDFs). A step never gets the same picture twice, so a picture Eric
    kept or discarded there isn't suggested again. Returns how many suggestions were added."""
    placed = repo.placed(session, version_id)
    added = 0
    for element_id, picture in repo.page_matches(session, version_id):
        key = (element_id, picture.stored_path)
        if key in placed or not _ensure_clean(picture.stored_path):
            continue
        repo.add(
            session,
            ImageRecord(
                element_id=element_id,
                stored_path=picture.stored_path,
                caption=picture.caption,
                origin="extracted",
                status=ImageStatus.SUGGESTED.value,
                source_id=picture.source_id,
                page=picture.page,
            ),
        )
        placed.add(key)
        added += 1
    return added


def version_images(sessions: Sessions, version_id: str) -> Result[list[ImageView]]:
    """The version's pictures in process order, for the map marker and the walkthrough strip."""
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        rank = {ElementKind.START.value: 0, ElementKind.END.value: 2}
        steps = sorted(map_repo.elements(session, version_id), key=lambda e: rank.get(e.kind, 1))
        order = {e.id: n for n, e in enumerate(steps)}
        found = sorted(
            repo.for_version(session, version_id),
            key=lambda i: order.get(i.element_id or "", len(order)),
        )
        return Ok(_views(session, found, version.engagement_id))
