"""Pictures on steps (PRD §3.3 `images`, constraint 11): check an upload, remove its metadata,
make a thumbnail. Pure: bytes in, bytes out; no files, no database.

Verified against Pillow 12.3.0: `Image.open` reads JPEG, PNG and WebP; `ImageOps.exif_transpose`
applies the EXIF orientation; `Image.frombytes` builds a fresh image from the pixels alone, so
nothing from the original file (EXIF with GPS, XMP, ICC, comments, text chunks) can come along;
`thumbnail` keeps the aspect ratio. `Image.MAX_IMAGE_PIXELS` guards against decompression bombs.
"""

from __future__ import annotations

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

from app.domain.result import Err, ErrorKind, Ok, Result

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
THUMB_SIDE = 480
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}

WRONG_TYPE = "Choose a JPG, PNG or WebP picture."
TOO_BIG = "Pictures can be up to 10 MB."
UNREADABLE = "That picture couldn't be opened. Save it again and upload the copy."
TOO_MANY_PIXELS = "Pictures can be up to 40 million pixels. Save a smaller copy and upload that."


class ImageFacts(BaseModel):
    format: str  # JPEG · PNG · WEBP
    extension: str
    media_type: str
    width: int
    height: int


def _invalid(message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": "file"})


def _open(data: bytes) -> Result[Image.Image]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            picture = Image.open(io.BytesIO(data))
            picture.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return _invalid(UNREADABLE)
    except (OSError, ValueError, SyntaxError):
        return _invalid(UNREADABLE)
    return Ok(picture)


def validate_image(data: bytes) -> Result[ImageFacts]:
    """A JPG, PNG or WebP picture of at most 10 MB and 40 million pixels that opens."""
    if len(data) > MAX_BYTES:
        return _invalid(TOO_BIG)
    match _open(data):
        case Err() as err:
            return err
        case Ok(value=picture):
            pass
    if picture.format not in FORMATS:
        return _invalid(WRONG_TYPE)
    width, height = picture.size
    if width * height > MAX_PIXELS:
        return _invalid(TOO_MANY_PIXELS)
    extension, media_type = FORMATS[picture.format]
    return Ok(ImageFacts(format=picture.format, extension=extension, media_type=media_type,
                         width=width, height=height))  # fmt: skip


def _clean(picture: Image.Image) -> Image.Image:
    """The pixels only, upright, in a mode every format can save."""
    upright = ImageOps.exif_transpose(picture)
    if upright.mode not in ("RGB", "RGBA", "L"):
        upright = upright.convert(
            "RGBA" if "A" in upright.getbands() or "transparency" in upright.info else "RGB"
        )
    return Image.frombytes(upright.mode, upright.size, upright.tobytes())


def _encode(picture: Image.Image, fmt: str) -> bytes:
    out = io.BytesIO()
    if fmt == "JPEG":
        picture.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
    elif fmt == "WEBP":
        picture.save(out, format="WEBP", quality=90)
    else:
        picture.save(out, format="PNG", optimize=True)
    return out.getvalue()


def strip_metadata(data: bytes) -> Result[bytes]:
    """The same picture, upright, re-encoded in its own format with no metadata at all."""
    match validate_image(data):
        case Err() as err:
            return err
        case Ok(value=facts):
            pass
    match _open(data):
        case Err() as err:
            return err
        case Ok(value=picture):
            return Ok(_encode(_clean(picture), facts.format))


def make_thumbnail(data: bytes, side: int = THUMB_SIDE) -> Result[bytes]:
    """A smaller copy (longest side `side` px) in the same format, with no metadata."""
    match validate_image(data):
        case Err() as err:
            return err
        case Ok(value=facts):
            pass
    match _open(data):
        case Err() as err:
            return err
        case Ok(value=picture):
            small = _clean(picture)
            small.thumbnail((side, side))
            return Ok(_encode(small, facts.format))
