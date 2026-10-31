"""Map another flow from these sources (2026-10-28, Eric's cargo manual; DECISIONS 81).

One engagement maps one flow. The next flow from the same documents starts with them as already
read (no reading job, no AI call), the same roles in the same lane order, the same names to hide
and conventions; its own name, trigger and end point. Nothing of the first map is copied, and the
first engagement is left exactly as it was. API_CONTRACT → POST /engagements/{id}/another-flow."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import AppConfig
from app.db import session_scope
from app.repositories.tables import AuditRow, Job, Source
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, with_key

PDF = "process_flow_diagram.pdf"
EXPORT = {"name": "Export", "trigger": "Cargo received for export",
          "end_point": "ULDs built up", "out_of_scope": "Import, transfer"}  # fmt: skip


@pytest.fixture()
def first(settings_config: AppConfig) -> Iterator[tuple[TestClient, Any]]:
    for client in make_client(settings_config):
        built = fixture_engagement.build(
            with_key(client), ["interview_transcript.txt", "sop_LC-07.docx", PDF]
        )
        client.patch(f"/api/engagements/{built.engagement_id}",
                     json={"conventions": {"granularity": "fine"}, "industry": "Air cargo",
                           "confidential_terms": ["Acme Ground Services"]})  # fmt: skip
        yield client, built


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_next_flow_starts_with_the_same_documents_roles_and_names(
    first: tuple[TestClient, Any],
) -> None:
    client, built = first
    eid = built.engagement_id
    made = client.post(f"/api/engagements/{eid}/another-flow", json=EXPORT)
    assert made.status_code == 201, made.text
    new = made.json()
    assert new["id"] != eid
    assert {k: new[k] for k in EXPORT} == EXPORT
    assert new["every_flow"] is False and new["industry"] == "Air cargo"
    assert new["conventions"]["granularity"] == "fine"
    assert new["confidential_terms"] == ["Acme Ground Services"]

    def roles(e: str) -> list[tuple[str, list[str]]]:
        return [(r["name"], r["aliases"]) for r in get(client, f"/api/engagements/{e}/roles")]

    assert roles(new["id"]) == roles(eid)
    terms = {(t["term"], t["replacement"]) for t in
             get(client, f"/api/engagements/{eid}/redaction-terms")}  # fmt: skip
    assert {(t["term"], t["replacement"]) for t in
            get(client, f"/api/engagements/{new['id']}/redaction-terms")} == terms  # fmt: skip
    assert ("Priya Nair", "Load controller") in terms  # the speaker's name stays hidden

    before = get(client, f"/api/engagements/{eid}/sources")
    after = get(client, f"/api/engagements/{new['id']}/sources")
    assert [(s["filename"], s["kind"], s["text_status"], s["segment_count"]) for s in after] == [
        (s["filename"], s["kind"], s["text_status"], s["segment_count"]) for s in before
    ]
    assert {s["id"] for s in after}.isdisjoint({s["id"] for s in before})
    pdf = next(s for s in after if s["filename"] == PDF)
    assert pdf["suggested_images"] == next(
        s for s in before if s["filename"] == PDF)["suggested_images"] > 0  # fmt: skip
    for old, copy in zip(before, after, strict=True):
        texts = [x["text"] for x in get(client, f"/api/sources/{old['id']}/segments")["segments"]]
        copied = get(client, f"/api/sources/{copy['id']}/segments")["segments"]
        assert [x["text"] for x in copied] == texts
    # Speakers stay mapped to the new engagement's roles.
    transcript = next(s for s in after if s["filename"] == "interview_transcript.txt")
    speakers = {s["label"]: s for s in get(client, f"/api/sources/{transcript['id']}/speakers")}
    new_roles = {r["name"]: r["id"] for r in get(client, f"/api/engagements/{new['id']}/roles")}
    assert speakers["Priya Nair"]["role_id"] == new_roles["Load controller"]

    # Ready to draft with nothing to read again (no reading job); nothing of a map copied.
    assert get(client, f"/api/engagements/{new['id']}/draft")["version"] is None
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        reads = session.scalars(select(Job).where(Job.engagement_id == new["id"])).all()
        assert reads == []
        rows = session.scalars(select(AuditRow).where(AuditRow.engagement_id == new["id"])).all()
        assert [r.action for r in rows] == ["Started another flow from these sources"]
        assert rows[0].after["from_engagement"] == "Load control"
        assert (rows[0].after["sources"], rows[0].after["roles"]) == (3, 5)


def test_the_files_are_copies_and_the_first_engagement_is_untouched(
    first: tuple[TestClient, Any], settings_config: AppConfig
) -> None:
    client, built = first
    eid = built.engagement_id
    new = client.post(f"/api/engagements/{eid}/another-flow", json=EXPORT).json()
    folder = settings_config.data_dir / "sources"
    assert sorted(p.name for p in (folder / new["id"]).iterdir()) and (folder / eid).is_dir()
    copied = next(s for s in get(client, f"/api/engagements/{new['id']}/sources")
                  if s["filename"] == PDF)  # fmt: skip
    assert client.delete(f"/api/sources/{copied['id']}").status_code == 204
    originals = get(client, f"/api/engagements/{eid}/sources")
    assert len(originals) == 3
    assert all(Path(p).is_file() for p in (folder / eid).iterdir())
    assert len(list((folder / eid).iterdir())) == 3


def test_a_name_is_needed_and_the_first_engagement_must_exist(
    first: tuple[TestClient, Any],
) -> None:
    client, built = first
    missing = client.post(f"/api/engagements/{built.engagement_id}/another-flow",
                          json={**EXPORT, "name": " "})  # fmt: skip
    assert missing.status_code == 422, missing.text
    gone = client.post("/api/engagements/nope/another-flow", json=EXPORT)
    assert gone.status_code == 404
    assert len(get(client, "/api/engagements")) == 1


def test_a_document_still_being_read_waits(first: tuple[TestClient, Any]) -> None:
    """A copy of a document still being read would never be read: Eric is asked to wait."""
    client, built = first
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        source = session.get(Source, built.sources[PDF])
        assert source is not None
        source.text_status = "pending"
    waiting = client.post(f"/api/engagements/{built.engagement_id}/another-flow", json=EXPORT)
    assert waiting.status_code == 409, waiting.text
    assert waiting.json()["error"]["message"] == (
        "process_flow_diagram.pdf is still being read. Try again when every document is ready."
    )
    assert len(get(client, "/api/engagements")) == 1
