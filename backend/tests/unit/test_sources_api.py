"""Sources: upload, reading, registry, delete, passages (API_CONTRACT.md → Sources)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import sources as source_actions
from app.config import AppConfig
from app.domain.enums import SourceKind
from app.main import create_app
from tests.paths import BACKEND_ROOT

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "engagement_load_control"


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


@pytest.fixture()
def engagement(client: TestClient) -> str:
    return str(client.post("/api/engagements", json={"name": "Load control"}).json()["id"])


def upload(
    client: TestClient, engagement: str, name: str, content: bytes | None = None, **form: Any
) -> Any:
    data = content if content is not None else (FIXTURES / name).read_bytes()
    return client.post(
        f"/api/engagements/{engagement}/sources",
        files={"file": (name, data, "application/octet-stream")},
        data={k: str(v).lower() if isinstance(v, bool) else v for k, v in form.items()},
    )


def db_count(config: AppConfig, table: str) -> int:
    with sqlite3.connect(config.data_dir / "app.db") as conn:
        return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_word_sop_is_read_with_clause_anchors(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    response = upload(
        client,
        engagement,
        "sop_LC-07.docx",
        version_date="2026-03-01",
        owner="Load Control",
        controlled_copy=True,
    )
    assert response.status_code == 201
    source = response.json()
    assert (source["kind"], source["format"], source["text_status"]) == ("sop", "docx", "ready")
    assert (source["filename"], source["segment_count"], source["controlled_copy"]) == (
        "sop_LC-07.docx",
        10,
        True,
    )
    stored = settings_config.data_dir / "sources" / engagement / f"{source['id']}.docx"
    assert stored.read_bytes() == (FIXTURES / "sop_LC-07.docx").read_bytes()
    page = client.get(f"/api/sources/{source['id']}/segments").json()
    assert page["total"] == 10 and page["coverage_pct"] is None
    anchors = {s["anchor"]: s["text"] for s in page["segments"]}
    assert anchors["§3.1"].startswith("§3.1 The Load Controller shall prepare")
    assert all(s["cited"] is False and s["speaker_role"] is None for s in page["segments"])


def test_pdf_flags_scanned_pages_and_suggests_its_image(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    source = upload(client, engagement, "manual_extract.pdf").json()
    assert source["kind"] == "manual" and source["text_status"] == "ready"
    assert source["ocr_pages"] == [2] and source["suggested_images"] == 1
    images = list((settings_config.data_dir / "images" / engagement).iterdir())
    assert len(images) == 1 and images[0].name.startswith(f"{source['id']}-p3-")
    segments = client.get(f"/api/sources/{source['id']}/segments").json()["segments"]
    assert {s["anchor"] for s in segments} == {"p. 1", "p. 3"}


def test_transcripts_wait_for_phase_p2(client: TestClient, engagement: str) -> None:
    source = upload(client, engagement, "interview_transcript.txt", b"[06:40] Speaker: text").json()
    assert source["kind"] == "interview_transcript"
    assert source["text_status"] == "pending" and source["segment_count"] == 0
    assert "phase P2" in source["error"]


def test_a_damaged_file_is_kept_and_marked_failed(client: TestClient, engagement: str) -> None:
    source = upload(client, engagement, "sop_broken.docx", b"not a word file").json()
    assert source["text_status"] == "failed"
    assert source["error"].startswith("The Word document could not be opened.")
    assert "upload it again" in source["error"]


@pytest.mark.parametrize(
    ("name", "content", "form", "message"),
    [
        ("plan.xlsx", b"x", {}, source_actions.BAD_FORMAT),
        ("sop.docx", b"", {}, source_actions.EMPTY),
        ("sop.docx", b"x", {"kind": "spreadsheet"}, source_actions.BAD_KIND),
        ("sop.docx", b"x", {"version_date": "1 March"}, source_actions.BAD_DATE),
        ("sop.docx", b"x", {"owner": "x" * 121}, source_actions.BAD_OWNER),
    ],
)
def test_refused_uploads_leave_nothing_behind(
    client: TestClient,
    engagement: str,
    settings_config: AppConfig,
    name: str,
    content: bytes,
    form: dict[str, str],
    message: str,
) -> None:
    response = upload(client, engagement, name, content, **form)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == message
    folder = settings_config.data_dir / "sources" / engagement
    assert not folder.exists() or list(folder.iterdir()) == []
    assert db_count(settings_config, "sources") == 0


def test_files_over_the_size_limit_are_refused(
    client: TestClient, engagement: str, settings_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source_actions, "MAX_BYTES", 10)
    response = upload(client, engagement, "sop.docx", b"x" * 11)
    assert (
        response.status_code == 422
        and response.json()["error"]["message"] == source_actions.TOO_BIG
    )
    assert list((settings_config.data_dir / "sources" / engagement).iterdir()) == []


def test_unknown_engagement_saves_nothing(client: TestClient, settings_config: AppConfig) -> None:
    response = upload(client, "nope", "sop_LC-07.docx")
    assert response.status_code == 404
    assert not (settings_config.data_dir / "sources" / "nope").exists()


def test_a_crafted_file_name_cannot_escape_the_data_folder(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    source = upload(
        client, engagement, "../../evil_sop.docx", (FIXTURES / "sop_RP-02.docx").read_bytes()
    ).json()
    assert source["filename"] == "evil_sop.docx"
    assert (settings_config.data_dir / "sources" / engagement / f"{source['id']}.docx").exists()
    assert not (settings_config.data_dir.parent / "evil_sop.docx").exists()


def test_registry_edit_and_delete(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    pdf = upload(client, engagement, "manual_extract.pdf").json()
    jd = upload(client, engagement, "jd_load_controller.docx").json()
    assert jd["kind"] == "job_description"
    listed = client.get(f"/api/engagements/{engagement}/sources").json()
    assert [s["id"] for s in listed] == [pdf["id"], jd["id"]]
    edited = client.patch(
        f"/api/sources/{pdf['id']}", json={"kind": "sop", "owner": "Ramp", "controlled_copy": True}
    )
    assert edited.status_code == 200
    assert (edited.json()["kind"], edited.json()["owner"], edited.json()["controlled_copy"]) == (
        "sop",
        "Ramp",
        True,
    )
    assert (
        client.patch(f"/api/sources/{pdf['id']}", json={"version_date": "soon"}).status_code == 422
    )
    assert client.delete(f"/api/sources/{pdf['id']}").status_code == 204
    assert client.get(f"/api/sources/{pdf['id']}").status_code == 404
    assert not (settings_config.data_dir / "sources" / engagement / f"{pdf['id']}.pdf").exists()
    assert list((settings_config.data_dir / "images" / engagement).iterdir()) == []
    assert db_count(settings_config, "images") == 0
    assert db_count(settings_config, "source_segments") == jd["segment_count"]
    assert client.delete(f"/api/sources/{pdf['id']}").status_code == 404


def test_deleting_the_engagement_removes_uploaded_files(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    upload(client, engagement, "manual_extract.pdf")
    assert client.delete(f"/api/engagements/{engagement}").status_code == 204
    assert not (settings_config.data_dir / "sources" / engagement).exists()
    assert not (settings_config.data_dir / "images" / engagement).exists()
    assert db_count(settings_config, "source_segments") == 0


def test_passages_are_paged(client: TestClient, engagement: str) -> None:
    source = upload(client, engagement, "sop_LC-07.docx").json()
    page = client.get(
        f"/api/sources/{source['id']}/segments", params={"page": 2, "page_size": 4}
    ).json()
    assert (page["total"], page["page"], page["pages"]) == (10, 2, 3)
    assert [s["seq"] for s in page["segments"]] == [5, 6, 7, 8]
    bad = client.get(f"/api/sources/{source['id']}/segments", params={"page": 0})
    assert bad.status_code == 422
    assert client.get("/api/sources/nope/segments").status_code == 404


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("interview_transcript.txt", SourceKind.INTERVIEW_TRANSCRIPT),
        ("call.vtt", SourceKind.INTERVIEW_TRANSCRIPT),
        ("sop_LC-07.docx", SourceKind.SOP),
        ("jd_load_controller.docx", SourceKind.JOB_DESCRIPTION),
        ("Job Description - Lead.pdf", SourceKind.JOB_DESCRIPTION),
        ("ops manual.pdf", SourceKind.MANUAL),
        ("notes.docx", SourceKind.OTHER),
        ("adjdjd.docx", SourceKind.OTHER),
    ],
)
def test_kind_is_guessed_from_the_file_name(name: str, kind: SourceKind) -> None:
    assert source_actions.guess_kind(name) is kind


def test_uploads_are_audited(
    client: TestClient, engagement: str, settings_config: AppConfig
) -> None:
    source = upload(client, engagement, "sop_RP-02.docx").json()
    client.patch(f"/api/sources/{source['id']}", json={"owner": "Ramp"})
    client.patch(f"/api/sources/{source['id']}", json={"owner": "Ramp"})
    client.delete(f"/api/sources/{source['id']}")
    with sqlite3.connect(settings_config.data_dir / "app.db") as conn:
        actions = [r[0] for r in conn.execute("SELECT action FROM audit_log ORDER BY created_at")]
    assert actions == [
        "Created engagement",
        "Added source",
        "Edited source details",
        "Deleted source",
    ]


def test_delete_never_touches_files_outside_the_data_folder(
    client: TestClient, engagement: str, settings_config: AppConfig, tmp_path: Path
) -> None:
    source = upload(client, engagement, "sop_RP-02.docx").json()
    outside = tmp_path / "outside.docx"
    outside.write_bytes(b"keep me")
    with sqlite3.connect(settings_config.data_dir / "app.db") as conn:
        conn.execute(
            "UPDATE sources SET stored_path = ? WHERE id = ?", (str(outside), source["id"])
        )
    assert client.delete(f"/api/sources/{source['id']}").status_code == 204
    assert outside.read_bytes() == b"keep me"
