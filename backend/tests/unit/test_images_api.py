"""Images on steps (API_CONTRACT.md → Images; PRD §4, constraint 11) on the illustrative Appendix A
draft, Claude mocked: the upload gate (422 naming the field), metadata removed from the stored file,
keep and discard of suggestions, remove, files, and drafts only."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import ExifTags, Image

from app.db import session_scope
from app.domain.models import ImageRecord
from app.repositories import images as images_repo
from app.repositories.tables import Image as ImageRow
from tests.services.test_images import jpeg_with_gps
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

GOOD = {
    "caption": "Load sheet on the ramp printer",
    "image_type": "workplace_photo",
    "redaction_confirmed": "true",
}

# The messages Eric reads, spelled out here rather than imported from the code under test.
HIDDEN_NAME = "The caption contains a name from your list of names to hide. Use the role instead."
CONFIRM = (
    "Confirm that faces, names, badge numbers and flight identifiers are removed or not shown."
)
UNREADABLE = "That picture couldn't be opened. Save it again and upload the copy."


def upload(
    d: Drafted, label: str = "Issue load sheet", data: bytes | None = None, **form: str
) -> Any:
    fields = {**GOOD, **form}
    fields = {k: v for k, v in fields.items() if v != "<none>"}
    return d.client.post(
        f"/api/elements/{d.ids[label]}/images",
        data=fields,
        files={"file": ("photo.jpg", data if data is not None else jpeg_with_gps(), "image/jpeg")},
    )


def stored(d: Drafted, image_id: str) -> Path:
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        image = images_repo.get(session, image_id)
    assert image is not None
    return Path(image.stored_path)


def suggestion(d: Drafted, label: str = "Draft load plan") -> str:
    """A PDF suggestion on a step (as increment 2 will attach them), with its own file."""
    folder = d.client.app.state.config.data_dir / "images" / d.engagement_id  # type: ignore[attr-defined]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "suggested.jpg"
    path.write_bytes(jpeg_with_gps())
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        record = images_repo.add(
            session,
            ImageRecord(
                element_id=d.ids[label],
                stored_path=str(path),
                caption="Image from sop_LC-07.docx, page 3",
                origin="extracted",
                status="suggested",
                page=3,
            ),
        )
    return record.id


def test_an_upload_is_stored_without_metadata_with_a_thumbnail(drafted: Drafted) -> None:
    response = upload(drafted)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["origin"], body["status"], body["image_type"], body["redaction_confirmed"]) == (
        "uploaded", "kept", "workplace_photo", True)  # fmt: skip
    path = stored(drafted, body["id"])
    with Image.open(path) as picture:
        assert picture.getexif().get_ifd(ExifTags.IFD.GPSInfo) == {}
        assert dict(picture.getexif()) == {}
        assert picture.size == (20, 40)  # stored upright
    assert b"CameraCo" not in path.read_bytes()
    assert path.with_name(f"{path.stem}.thumb{path.suffix}").exists()
    assert drafted.audit()[0]["action"] == "Added image"
    listed = drafted.client.get(f"/api/elements/{drafted.ids['Issue load sheet']}/images").json()
    assert [i["id"] for i in listed] == [body["id"]]
    detail = drafted.client.get(f"/api/elements/{drafted.ids['Issue load sheet']}").json()
    assert detail["image_count"] == 1


def test_the_file_and_its_thumbnail_are_served_without_metadata(drafted: Drafted) -> None:
    big = io.BytesIO()
    Image.new("RGB", (1200, 600)).save(big, format="PNG")
    image_id = upload(drafted, data=big.getvalue()).json()["id"]
    full = drafted.client.get(f"/api/images/{image_id}/file")
    assert full.status_code == 200 and full.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(full.content)) as picture:
        assert picture.size == (1200, 600)
    thumb = drafted.client.get(f"/api/images/{image_id}/file?size=thumb")
    with Image.open(io.BytesIO(thumb.content)) as picture:
        assert picture.size == (480, 240)
    assert drafted.client.get("/api/images/nope/file").status_code == 404


@pytest.mark.parametrize(
    ("form", "data", "field", "message"),
    [
        ({"caption": "  "}, None, "caption", "Add a caption of up to 300 characters."),
        ({"caption": "x" * 301}, None, "caption", "Add a caption of up to 300 characters."),
        ({"caption": "Priya Nair at the printer"}, None, "caption",
         HIDDEN_NAME),
        ({"image_type": "<none>"}, None, "image_type", "Choose what kind of picture this is."),
        ({"image_type": "selfie"}, None, "image_type", "Choose what kind of picture this is."),
        ({"redaction_confirmed": "<none>"}, None, "redaction_confirmed",
         CONFIRM),
        ({"redaction_confirmed": "false"}, None, "redaction_confirmed",
         CONFIRM),
        ({}, b"GIF89a not really", "file", UNREADABLE),
        ({}, b"", "file", "Choose a JPG, PNG or WebP picture."),
    ],
)  # fmt: skip
def test_the_upload_gate_names_the_field(
    drafted: Drafted, form: dict[str, str], data: bytes | None, field: str, message: str
) -> None:
    response = upload(drafted, data=data, **form)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert (error["details"]["field"], error["message"]) == (field, message)
    assert "Priya" not in response.text
    data_dir = drafted.client.app.state.config.data_dir  # type: ignore[attr-defined]
    assert not list((data_dir / "images").glob("**/*")) or all(
        p.is_dir() for p in (data_dir / "images").glob("**/*")
    )


def test_start_and_end_carry_no_pictures(drafted: Drafted) -> None:
    response = upload(drafted, label="Flight scheduled")
    assert response.status_code == 422
    missing = drafted.client.post(
        "/api/elements/nope/images",
        data=GOOD,
        files={"file": ("a.jpg", jpeg_with_gps(), "image/jpeg")},
    )
    assert missing.status_code == 404


def test_a_suggestion_is_kept_with_type_and_confirmation_or_discarded(drafted: Drafted) -> None:
    kept_id = suggestion(drafted)
    listed = drafted.client.get(f"/api/elements/{drafted.ids['Draft load plan']}/images").json()
    assert listed[0]["status"] == "suggested" and listed[0]["page"] == 3
    missing = drafted.client.patch(f"/api/images/{kept_id}", json={"status": "kept"})
    assert (
        missing.status_code == 422 and missing.json()["error"]["details"]["field"] == "image_type"
    )
    unconfirmed = drafted.client.patch(
        f"/api/images/{kept_id}", json={"status": "kept", "image_type": "document_extract"}
    )
    assert unconfirmed.json()["error"]["details"]["field"] == "redaction_confirmed"
    kept = drafted.client.patch(f"/api/images/{kept_id}", json={
        "status": "kept", "image_type": "document_extract", "redaction_confirmed": True,
        "caption": "Weight and balance form"}).json()  # fmt: skip
    assert (kept["status"], kept["caption"], kept["redaction_confirmed"]) == (
        "kept",
        "Weight and balance form",
        True,
    )
    assert drafted.audit()[0]["action"] == "Kept suggested image"
    back = drafted.client.patch(f"/api/images/{kept_id}", json={"status": "suggested"})
    assert back.status_code == 422
    other = suggestion(drafted, "Issue load sheet")
    gone = drafted.client.patch(f"/api/images/{other}", json={"status": "discarded"}).json()
    assert gone["status"] == "discarded"
    assert (
        drafted.client.get(f"/api/elements/{drafted.ids['Issue load sheet']}/images").json() == []
    )
    removal = drafted.client.delete(f"/api/images/{kept_id}")
    assert (
        removal.json()["error"]["message"] == "Discard a suggested picture instead of removing it."
    )


def test_an_open_suggestion_blocks_publishing(drafted: Drafted) -> None:
    suggestion(drafted)
    for label, element_id in drafted.ids.items():
        if label not in ("Flight scheduled", "Final load sheet issued"):
            drafted.client.post(f"/api/elements/{element_id}/confirm")
    blocked = drafted.client.post(f"/api/versions/{drafted.version_id}/publish")
    assert [b["type"] for b in blocked.json()["error"]["details"]["blockers"]] == [
        "suggested_image"
    ]


def test_removing_an_upload_deletes_its_file_unless_shared(drafted: Drafted) -> None:
    first = upload(drafted).json()["id"]
    path = stored(drafted, first)
    assert drafted.client.delete(f"/api/images/{first}").status_code == 204
    assert not path.exists() and not path.with_name(f"{path.stem}.thumb{path.suffix}").exists()
    assert drafted.audit()[0]["action"] == "Removed image"
    second = upload(drafted).json()["id"]
    shared = stored(drafted, second)
    with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        session.add(ImageRow(element_id=drafted.ids["Draft load plan"], stored_path=str(shared),
                             origin="uploaded", status="kept"))  # fmt: skip
    drafted.client.delete(f"/api/images/{second}")
    assert shared.exists()  # another version still uses it


def test_captions_change_and_published_versions_refuse_changes(drafted: Drafted) -> None:
    image_id = upload(drafted).json()["id"]
    renamed = drafted.client.patch(f"/api/images/{image_id}", json={"caption": "Printer at gate 5"})
    assert renamed.json()["caption"] == "Printer at gate 5"
    for label, element_id in drafted.ids.items():
        if label not in ("Flight scheduled", "Final load sheet issued"):
            drafted.client.post(f"/api/elements/{element_id}/confirm")
    assert drafted.client.post(f"/api/versions/{drafted.version_id}/publish").status_code == 200
    refused = drafted.client.patch(f"/api/images/{image_id}", json={"caption": "Other"})
    assert refused.status_code == 409
    assert upload(drafted).status_code == 409
    assert drafted.client.delete(f"/api/images/{image_id}").status_code == 409
    # Published images stay visible in the app, and never reach an export.
    assert drafted.client.get(f"/api/images/{image_id}/file").status_code == 200
    for fmt in ("md", "json", "csv", "html"):
        text = drafted.client.get(f"/api/versions/{drafted.version_id}/export/{fmt}").text
        assert image_id not in text and "Printer at gate 5" not in text and ".jpg" not in text
