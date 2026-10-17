"""Working spreadsheets and email threads as sources (P10b R11; criterion 92; API_CONTRACT.md →
Sources): upload, the kind guessed, anchored passages, email names hidden, senders mapped to
roles, and the frontend sample written from what the backend sends."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import sources as source_actions
from app.config import AppConfig
from app.main import create_app
from app.services import parsing
from tests import artefacts
from tests.uploads import upload


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


@pytest.fixture()
def engagement(client: TestClient) -> str:
    eid = str(client.post("/api/engagements", json={"name": "Load control"}).json()["id"])
    for name in ("Load controller", "Ramp"):
        assert client.post(f"/api/engagements/{eid}/roles", json={"name": name}).status_code == 201
    return eid


def segments(client: TestClient, source_id: str) -> list[dict[str, Any]]:
    return list(client.get(f"/api/sources/{source_id}/segments").json()["segments"])


def terms(client: TestClient, engagement: str) -> dict[str, str]:
    rows = client.get(f"/api/engagements/{engagement}/redaction-terms").json()
    return {r["term"]: r["origin"] for r in rows}


def test_a_spreadsheet_is_a_working_spreadsheet_with_sheet_cell_anchors(
    client: TestClient, engagement: str
) -> None:
    source = upload(client, engagement, "Load plan tracker.xlsx", artefacts.make_xlsx()).json()
    assert (source["kind"], source["format"], source["text_status"]) == (
        "working_spreadsheet", "xlsx", "ready",
    )  # fmt: skip
    assert source["segment_count"] == 6
    found = {s["anchor"]: (s["section"], s["text"]) for s in segments(client, source["id"])}
    assert found["Plan!A4"] == (
        "Plan",
        "Flight: SQ 221 | Step: Draft load plan | Owner: Load controller | Minutes: 20 "
        "| Date: 2026-03-02",
    )
    assert found["'Shift log'!A2"][0] == "Shift log"
    assert client.get(f"/api/sources/{source['id']}/speakers").json() == []


def test_a_csv_is_a_working_spreadsheet_anchored_by_row(
    client: TestClient, engagement: str
) -> None:
    source = upload(client, engagement, "tracker.csv", artefacts.CSV).json()
    assert (source["kind"], source["format"], source["segment_count"]) == (
        "working_spreadsheet", "csv", 3,
    )  # fmt: skip
    assert [s["anchor"] for s in segments(client, source["id"])] == ["row 1", "row 2", "row 4"]


def test_an_email_hides_people_not_teams_and_maps_senders_to_roles(
    client: TestClient, engagement: str
) -> None:
    source = upload(client, engagement, "Re Load plan revision.eml", artefacts.make_eml()).json()
    assert (source["kind"], source["format"], source["segment_count"]) == ("email_thread", "eml", 7)
    hidden = terms(client, engagement)
    # Every address, and display names that look like a person's name: not teams or roles.
    assert hidden == {
        "Tan, Wei Ming": "email_header", "Wei Ming Tan": "email_header",
        "weiming.tan@example.com": "email_header", "lc.ops@example.com": "email_header",
        "ramp.lead@example.com": "email_header", "Priya Nair": "email_header",
        "priya.nair@example.com": "email_header", "lc@example.com": "email_header",
        "ops.desk@example.com": "email_header", "Kumar, Ravi": "email_header",
        "Ravi Kumar": "email_header",
    }  # fmt: skip
    shown = segments(client, source["id"])
    assert shown[0]["text"] == (
        "From: [name] · To: LC Ops Desk, [name] · Cc: [name] · Sent: 2026-03-03 09:14 +08:00 · "
        "Subject: Load plan revision SQ 221"
    )
    assert [s["speaker_role"] for s in shown] == [None, None, None, None, None, None, None]
    speakers = client.get(f"/api/sources/{source['id']}/speakers").json()
    assert [(s["label"], s["segment_count"]) for s in speakers] == [
        ("Tan, Wei Ming", 2), ("Priya Nair", 1), ("Ramp Lead", 1), ("Ops Desk", 1),
    ]  # fmt: skip
    roles = {r["name"]: r["id"] for r in client.get(f"/api/engagements/{engagement}/roles").json()}
    mapped = client.put(
        f"/api/sources/{source['id']}/speakers",
        json={"Tan, Wei Ming": roles["Load controller"], "Ramp Lead": roles["Ramp"]},
    )
    assert mapped.status_code == 200
    shown = segments(client, source["id"])
    assert shown[0]["text"].startswith("From: Load controller · To: LC Ops Desk, [name] ·")
    assert [s["speaker_role"] for s in shown[1:4]] == ["Load controller", "Load controller", None]
    assert shown[5]["speaker_role"] == "Ramp"
    # Names stay out of the file name shown outside the owner-only places.
    named = upload(client, engagement, "Priya Nair notes.eml", artefacts.make_html_eml()).json()
    assert named["filename"] == "[name] notes.eml" and named["kind"] == "email_thread"


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("empty.csv", b",,\n", parsing.NO_CELLS),
        ("notes.eml", b"just words\n", parsing.NOT_AN_EMAIL),
        ("broken.xlsx", b"not a zip", "The spreadsheet could not be opened."),
    ],
)
def test_a_file_that_cannot_be_read_is_kept_as_failed_with_the_reason(
    client: TestClient, engagement: str, name: str, data: bytes, message: str
) -> None:
    source = upload(client, engagement, name, data).json()
    assert source["text_status"] == "failed"
    assert source["error"] == message + source_actions.CANT_READ_TAIL


def test_other_formats_are_refused_with_the_list(client: TestClient, engagement: str) -> None:
    for name in ("old.xls", "macro.xlsm", "outlook.msg"):
        response = upload(client, engagement, name, b"data")
        assert response.status_code == 422
        assert response.json()["error"]["message"] == (
            "Process Map Studio reads .docx, .pdf, .txt, .vtt, .srt, .xlsx, .csv and .eml files."
        )


def test_a_spreadsheet_counts_as_a_process_document_for_readiness(
    client: TestClient, engagement: str
) -> None:
    upload(client, engagement, "tracker.xlsx", artefacts.make_xlsx()).json()
    missing = client.get(f"/api/engagements/{engagement}/readiness").json()["missing"]
    assert not any("process document" in m for m in missing)


def test_the_frontend_artefact_sample_matches_the_backend(
    client: TestClient, engagement: str
) -> None:
    """frontend/tests/fixtures/artefact_sources.json: the source objects, passages, speakers and
    names list exactly as the backend sends them for a spreadsheet and an email (R11), so the
    Sources screen tests use real shapes. Not a PRD baseline. Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    sheet = upload(client, engagement, "Load plan tracker.xlsx", artefacts.make_xlsx()).json()
    email = upload(client, engagement, "Re Load plan revision.eml", artefacts.make_eml()).json()
    bundle = {
        "sources": client.get(f"/api/engagements/{engagement}/sources").json(),
        "sheet_segments": client.get(f"/api/sources/{sheet['id']}/segments").json(),
        "email_segments": client.get(f"/api/sources/{email['id']}/segments").json(),
        "email_speakers": client.get(f"/api/sources/{email['id']}/speakers").json(),
        "redaction_terms": client.get(f"/api/engagements/{engagement}/redaction-terms").json(),
    }
    text = json.dumps(bundle)
    fixed = json.loads(
        text.replace(sheet["created_at"], "2026-10-13T00:00:00+00:00").replace(
            email["created_at"], "2026-10-13T00:00:00+00:00"
        )
    )
    matches_baseline("artefact_sources.json", fixed, FRONTEND_FIXTURES)
