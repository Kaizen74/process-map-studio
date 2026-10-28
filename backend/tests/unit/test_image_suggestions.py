"""Pictures suggested from PDFs (API_CONTRACT.md → Suggested images from PDFs, GET
/versions/{vid}/images; PRD §3.7 S0, §6.3 P8, Q6) on the illustrative Appendix A draft, Claude
mocked. The sample has no PDF pictures, so each test gives one passage a page and saves a picture
for that page of its source, as reading a PDF would."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import ExifTags, Image
from sqlalchemy import select, update

from app.actions import images as images_action
from app.db import session_scope
from app.domain.models import ImageRecord
from app.repositories import elements as map_repo
from app.repositories import images as images_repo
from app.repositories.tables import EvidenceLink, Source, SourceSegment
from app.services import images as pictures
from app.services.images import thumb_path
from tests.services.test_images import jpeg_with_gps
from tests.unit.test_images_api import upload
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_refresh import ids_by_label, refresh

__all__ = ["drafted"]

PAGE = 7


def sessions(d: Drafted) -> Any:
    return d.client.app.state.sessions  # type: ignore[attr-defined]


def clean_jpeg() -> bytes:
    """A picture as reading a PDF now saves it: no metadata."""
    return pictures.strip_metadata(jpeg_with_gps()).value  # type: ignore[union-attr,no-any-return]


def pdf_picture(d: Drafted, label: str, data: bytes | None = None, clean: bool = True) -> Path:
    """Give the first verified passage behind `label` page 7 and save a picture for that page of
    its source. `clean=False` stores it as found, with no thumbnail (a file read before P8)."""
    folder = d.client.app.state.config.data_dir / "images" / d.engagement_id  # type: ignore[attr-defined]
    folder.mkdir(parents=True, exist_ok=True)
    with session_scope(sessions(d)) as session:
        segment_id, source_id = session.execute(
            select(SourceSegment.id, SourceSegment.source_id)
            .join(EvidenceLink, EvidenceLink.segment_id == SourceSegment.id)
            .where(EvidenceLink.element_id == d.ids[label], EvidenceLink.verified.is_(True))
            .order_by(SourceSegment.seq)
        ).first()  # type: ignore[misc]
        session.execute(
            update(SourceSegment).where(SourceSegment.id == segment_id).values(page=PAGE)
        )
        filename = session.scalar(select(Source.filename).where(Source.id == source_id))
        path = folder / f"{source_id}-p{PAGE}-1.jpg"
        if clean:
            path.write_bytes(clean_jpeg())
            thumb_path(str(path)).write_bytes(clean_jpeg())
        else:
            path.write_bytes(data if data is not None else jpeg_with_gps())
        images_repo.add(
            session,
            ImageRecord(
                source_id=source_id,
                stored_path=str(path),
                page=PAGE,
                caption=f"Image from {filename}, page {PAGE}",
                origin="extracted",
                status="suggested",
            ),
        )
    return path


def attach(d: Drafted, version_id: str | None = None) -> int:
    with session_scope(sessions(d)) as session:
        return images_action.attach_suggestions(session, version_id or d.version_id)


def on_step(d: Drafted, label: str, ids: dict[str, str] | None = None) -> list[dict[str, Any]]:
    element_id = (ids or d.ids)[label]
    response = d.client.get(f"/api/elements/{element_id}/images")
    assert response.status_code == 200, response.text
    return list(response.json())


def version_images(d: Drafted, version_id: str | None = None) -> list[dict[str, Any]]:
    response = d.client.get(f"/api/versions/{version_id or d.version_id}/images")
    assert response.status_code == 200, response.text
    return list(response.json())


def open_suggestions(d: Drafted) -> int:
    with session_scope(sessions(d)) as session:
        return map_repo.suggested_image_count(session, d.version_id)


def test_a_pdf_picture_is_suggested_on_the_step_citing_its_page_once(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan")
    assert attach(drafted) >= 1
    [suggested] = on_step(drafted, "Draft load plan")
    assert (suggested["origin"], suggested["status"], suggested["page"]) == (
        "extracted",
        "suggested",
        PAGE,
    )
    assert suggested["caption"] == f"Image from {suggested['source_name']}, page {PAGE}"
    assert suggested["source_name"] and suggested["image_type"] is None
    assert on_step(drafted, "Flight scheduled") == []  # start and end carry no pictures
    # Never twice on a step, and a discarded one isn't suggested again.
    assert attach(drafted) == 0
    drafted.client.patch(f"/api/images/{suggested['id']}", json={"status": "discarded"})
    assert attach(drafted) == 0 and on_step(drafted, "Draft load plan") == []


def test_steps_citing_other_pages_get_nothing(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan")
    attach(drafted)
    pictured = {i["element_id"] for i in version_images(drafted)}
    labels = {v: k for k, v in drafted.ids.items()}
    assert "Draft load plan" in {labels[e] for e in pictured}
    # Every pictured step cites a verified passage on that page of that source.
    with session_scope(sessions(drafted)) as session:
        for element_id in pictured:
            pages = session.scalars(
                select(SourceSegment.page)
                .join(EvidenceLink, EvidenceLink.segment_id == SourceSegment.id)
                .where(EvidenceLink.element_id == element_id, EvidenceLink.verified.is_(True))
            ).all()
            assert PAGE in pages


def test_rejected_steps_get_no_suggestions_and_theirs_dont_block(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan")
    drafted.act("Draft load plan", "reject")
    attach(drafted)
    assert on_step(drafted, "Draft load plan") == []
    drafted.act("Draft load plan", "restore")
    attach(drafted)
    assert [i["status"] for i in on_step(drafted, "Draft load plan")] == ["suggested"]
    before = open_suggestions(drafted)
    drafted.act("Draft load plan", "reject")
    # Rejected: off the map, so its suggestion is neither counted in Q6 nor listed.
    assert open_suggestions(drafted) == before - 1
    assert drafted.ids["Draft load plan"] not in {i["element_id"] for i in version_images(drafted)}
    blockers = publish(drafted).json()["error"]["details"]["blockers"]
    assert ("suggested_image" in [b["type"] for b in blockers]) == (open_suggestions(drafted) > 0)


def test_a_picture_saved_before_p8_is_cleaned_when_first_suggested(drafted: Drafted) -> None:
    path = pdf_picture(drafted, "Draft load plan", clean=False)
    assert b"CameraCo" in path.read_bytes() and not thumb_path(str(path)).exists()
    attach(drafted)
    assert on_step(drafted, "Draft load plan")
    assert b"CameraCo" not in path.read_bytes() and thumb_path(str(path)).exists()
    with Image.open(path) as picture:
        assert dict(picture.getexif()) == {}
        assert picture.getexif().get_ifd(ExifTags.IFD.GPSInfo) == {}


def test_a_saved_picture_that_cant_be_opened_is_not_suggested(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan", data=b"not a picture", clean=False)
    assert attach(drafted) == 0 and on_step(drafted, "Draft load plan") == []


def test_the_version_lists_its_pictures_in_process_order(drafted: Drafted) -> None:
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    order = [e["id"] for e in graph["elements"]]
    upload(drafted, label="Issue load sheet")
    upload(drafted, label="Draft load plan", caption="Load plan on screen")
    pdf_picture(drafted, "Draft load plan")
    attach(drafted)
    listed = version_images(drafted)
    positions = [order.index(i["element_id"]) for i in listed]
    assert positions == sorted(positions)
    first_step = [i for i in listed if i["element_id"] == drafted.ids["Draft load plan"]]
    assert first_step[0]["status"] == "suggested"  # suggestions first within a step
    drafted.client.patch(f"/api/images/{first_step[0]['id']}", json={"status": "discarded"})
    assert first_step[0]["id"] not in {i["id"] for i in version_images(drafted)}
    missing = drafted.client.get("/api/versions/nope/images")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "That version doesn't exist."


def test_refresh_suggests_pictures_and_moves_them_to_the_fresh_step(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan")
    uploaded = upload(drafted, label="Issue load sheet").json()
    job = refresh(drafted)  # the draft job attaches the suggestion; nothing was attached before
    assert job["status"] == "done", job
    fresh = ids_by_label(drafted)
    assert fresh["Issue load sheet"] != drafted.ids["Issue load sheet"]  # replaced, unreviewed
    assert [i["id"] for i in on_step(drafted, "Issue load sheet", fresh)] == [uploaded["id"]]
    [suggested] = on_step(drafted, "Draft load plan", fresh)
    drafted.client.patch(f"/api/images/{suggested['id']}", json={"status": "discarded"})
    # Refreshed again: the discard travels with the step, so the picture isn't suggested again.
    assert refresh(drafted)["status"] == "done"
    again = ids_by_label(drafted)
    assert on_step(drafted, "Draft load plan", again) == []
    assert [i["id"] for i in on_step(drafted, "Issue load sheet", again)] == [uploaded["id"]]


def test_a_kept_suggestion_is_published_and_carried_by_reopen(drafted: Drafted) -> None:
    pdf_picture(drafted, "Draft load plan")
    attach(drafted)
    for image in version_images(drafted):
        kept = drafted.client.patch(
            f"/api/images/{image['id']}",
            json={
                "status": "kept",
                "image_type": "document_extract",
                "redaction_confirmed": True,
            },
        )
        assert kept.status_code == 200, kept.text
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    published = version_images(drafted)
    assert published and all(i["status"] == "kept" for i in published)
    reopened = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen").json()
    copied = version_images(drafted, reopened["id"])
    assert [(i["caption"], i["status"], i["page"]) for i in copied] == [
        (i["caption"], i["status"], i["page"]) for i in published
    ]
    assert attach(drafted, reopened["id"]) == 0  # already there, kept


def test_a_picture_is_suggested_once_however_many_steps_cite_its_page(drafted: Drafted) -> None:
    """2026-10-28 (Eric): a process-flow page cited by every step made each of its pictures a
    suggestion on every step (72 decisions on one manual). A picture is now suggested once, on
    the first step that cites its page."""
    pdf_picture(drafted, "Draft load plan")
    with session_scope(sessions(drafted)) as session:
        source_id = session.scalar(
            select(SourceSegment.source_id).where(SourceSegment.page == PAGE)
        )
        others = session.scalars(
            select(SourceSegment.id)
            .join(EvidenceLink, EvidenceLink.segment_id == SourceSegment.id)
            .where(
                EvidenceLink.element_id == drafted.ids["Special loads OK?"],
                EvidenceLink.verified.is_(True),
                SourceSegment.source_id == source_id,
            )
        ).all()
        assert others  # both steps cite the same source
        session.execute(update(SourceSegment).where(SourceSegment.id.in_(others)).values(page=PAGE))
    assert attach(drafted) == 1
    pictured = [i["element_id"] for i in version_images(drafted)]
    assert pictured == [drafted.ids["Draft load plan"]]
    assert attach(drafted) == 0  # nor again on the next step


def test_every_open_suggestion_is_discarded_in_one_go(drafted: Drafted) -> None:
    """2026-10-28 (Eric): "Discard all suggested pictures" on Review, one audit row."""
    pdf_picture(drafted, "Draft load plan")
    attach(drafted)
    assert open_suggestions(drafted) == 1
    url = f"/api/versions/{drafted.version_id}/images/discard-suggestions"
    response = drafted.client.post(url)
    assert response.status_code == 200, response.text
    assert response.json() == {"discarded": 1}
    assert open_suggestions(drafted) == 0 and on_step(drafted, "Draft load plan") == []
    assert attach(drafted) == 0  # a discarded picture isn't suggested again
    rows = [r for r in drafted.audit() if r["action"] == "Discarded all suggested images"]
    assert [r["after"] for r in rows] == [{"count": 1}]
    assert drafted.client.post(url).json() == {"discarded": 0}
    missing = drafted.client.post("/api/versions/nope/images/discard-suggestions")
    assert missing.status_code == 404


def test_a_published_version_keeps_its_suggestions_decisions(drafted: Drafted) -> None:
    confirm_all(drafted)
    publish(drafted)
    response = drafted.client.post(f"/api/versions/{drafted.version_id}/images/discard-suggestions")
    assert response.status_code == 409
