"""Pictures (PRD §3.3 `images`, constraint 11): only JPG, PNG and WebP up to 10 MB that open;
every piece of metadata (EXIF with GPS, text chunks) removed; the orientation applied; thumbnails
small and clean."""

from __future__ import annotations

import io

import pytest
from PIL import ExifTags, Image, PngImagePlugin

from app.domain.result import Ok
from app.services import images


def jpeg_with_gps(size: tuple[int, int] = (40, 20), orientation: int = 6) -> bytes:
    picture = Image.new("RGB", size, (200, 10, 10))
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = orientation
    exif[ExifTags.Base.Make] = "CameraCo"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (1.0, 21.0, 30.0)
    out = io.BytesIO()
    picture.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def encoded(
    fmt: str, size: tuple[int, int] = (30, 30), mode: str = "RGB", **params: object
) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size).save(out, format=fmt, **params)
    return out.getvalue()


def opened(data: bytes) -> Image.Image:
    picture = Image.open(io.BytesIO(data))
    picture.load()
    return picture


def test_the_photo_loses_gps_and_every_exif_field_and_stands_upright() -> None:
    original = jpeg_with_gps()
    assert opened(original).getexif().get_ifd(ExifTags.IFD.GPSInfo)  # the fixture does carry GPS
    clean = images.strip_metadata(original).value  # type: ignore[union-attr]
    picture = opened(clean)
    assert picture.format == "JPEG"
    assert dict(picture.getexif()) == {}
    assert picture.getexif().get_ifd(ExifTags.IFD.GPSInfo) == {}
    assert b"CameraCo" not in clean and b"Exif" not in clean
    assert picture.size == (20, 40)  # orientation 6 applied: turned upright


def test_png_text_chunks_and_webp_exif_are_removed_too() -> None:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Priya Nair")
    png = encoded("PNG", pnginfo=info)
    assert b"Priya" in png
    clean_png = images.strip_metadata(png).value  # type: ignore[union-attr]
    assert b"Priya" not in clean_png and opened(clean_png).format == "PNG"
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "CameraCo"
    webp = encoded("WEBP", exif=exif)
    assert b"CameraCo" in webp
    clean_webp = images.strip_metadata(webp).value  # type: ignore[union-attr]
    assert b"CameraCo" not in clean_webp and opened(clean_webp).format == "WEBP"


def test_transparent_and_palette_pictures_keep_their_look() -> None:
    rgba = images.strip_metadata(encoded("PNG", mode="RGBA")).value  # type: ignore[union-attr]
    assert opened(rgba).mode == "RGBA"
    palette = images.strip_metadata(encoded("PNG", mode="P")).value  # type: ignore[union-attr]
    assert opened(palette).mode in ("RGB", "RGBA")


def test_thumbnails_are_small_clean_and_keep_the_shape() -> None:
    big = encoded("JPEG", size=(1200, 600))
    thumb = opened(images.make_thumbnail(big).value)  # type: ignore[union-attr]
    assert thumb.size == (480, 240)
    assert opened(images.make_thumbnail(jpeg_with_gps()).value).getexif() == {}  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (encoded("GIF"), images.WRONG_TYPE),
        (encoded("BMP"), images.WRONG_TYPE),
        (b"not a picture at all", images.UNREADABLE),
        (encoded("JPEG")[:40], images.UNREADABLE),
        (b"\0" * (images.MAX_BYTES + 1), images.TOO_BIG),
    ],
)
def test_only_readable_jpg_png_and_webp_are_accepted(data: bytes, message: str) -> None:
    result = images.validate_image(data)
    assert result.message == message  # type: ignore[union-attr]
    assert result.details == {"field": "file"}  # type: ignore[union-attr]


def test_huge_pictures_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(images, "MAX_PIXELS", 100)
    assert images.validate_image(encoded("PNG", size=(20, 20))).message == images.TOO_MANY_PIXELS  # type: ignore[union-attr]


def test_the_facts_of_a_good_picture() -> None:
    facts = images.validate_image(encoded("WEBP", size=(64, 32))).value  # type: ignore[union-attr]
    assert (facts.format, facts.extension, facts.media_type, facts.width, facts.height) == (
        "WEBP", "webp", "image/webp", 64, 32)  # fmt: skip


# --- Pictures taken out of PDFs (P8 increment 2) --------------------------------------------------


def test_a_pdf_picture_keeps_a_web_format_and_loses_its_metadata() -> None:
    clean, facts = images.clean_extracted(jpeg_with_gps()).value  # type: ignore[union-attr,misc]
    picture = opened(clean)
    assert (picture.format, facts.extension, facts.media_type) == ("JPEG", "jpg", "image/jpeg")
    assert dict(picture.getexif()) == {} and b"CameraCo" not in clean
    assert picture.size == (20, 40) == (facts.width, facts.height)


def test_other_pdf_picture_formats_become_png_without_metadata() -> None:
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "ScannerCo"
    tiff = encoded("TIFF", exif=exif)
    assert b"ScannerCo" in tiff
    clean, facts = images.clean_extracted(tiff).value  # type: ignore[union-attr,misc]
    assert (opened(clean).format, facts.extension) == ("PNG", "png")
    assert b"ScannerCo" not in clean
    assert images.clean_extracted(encoded("BMP")).value[1].extension == "png"  # type: ignore[union-attr]


def test_pdf_pictures_have_no_byte_limit_but_the_pixel_limit_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(images, "MAX_BYTES", 10)
    png = encoded("PNG")
    assert isinstance(images.clean_extracted(png), Ok)
    assert isinstance(images.picture_facts(png), Ok)
    assert isinstance(images.make_thumbnail(png), Ok)
    assert images.validate_image(png).message == images.TOO_BIG  # type: ignore[union-attr]
    monkeypatch.setattr(images, "MAX_PIXELS", 100)
    assert images.clean_extracted(png).message == images.TOO_MANY_PIXELS  # type: ignore[union-attr]
    assert images.clean_extracted(b"%PDF not a picture").message == images.UNREADABLE  # type: ignore[union-attr]


def test_the_thumbnail_sits_next_to_the_picture() -> None:
    assert images.thumb_path("/data/images/e/p3-1.png").name == "p3-1.thumb.png"
