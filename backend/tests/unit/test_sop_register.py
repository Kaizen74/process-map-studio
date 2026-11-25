"""The SOP register and the process owner (PRD §3.20; DECISIONS 110): roles, not people; review
dates; controlled copy only once known; the newest of the same SOP counts once."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.domain.models import SourceView
from app.services import sop_register
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client

SOP_FILES = ["sop_LC-07.docx", "sop_RP-02.docx", "jd_load_controller.docx"]


def view(**fields: Any) -> SourceView:
    base: dict[str, Any] = {
        "id": "s1", "engagement_id": "e", "kind": "sop", "filename": "sop_LC-07.docx",
        "format": "docx", "mime": "", "version_date": "", "owner": "", "controlled_copy": False,
        "text_status": "ready", "error": "", "segment_count": 0, "ocr_pages": [],
        "suggested_images": 0, "created_at": "2026-01-01T00:00:00",
    }  # fmt: skip
    return SourceView(**{**base, **fields})


def test_the_register_rules() -> None:
    roles = {"r1": "Load control lead", "r2": "Quality manager"}
    found = sop_register.entries(
        [
            view(
                id="a",
                owner_role_id="r1",
                updated_by_role_id="r2",
                review_due="2026-03",
                controlled_copy=True,
                version_date="2025-01",
            ),
            view(id="b", filename="sop_RP-02.docx", owner="Ramp lead", review_due="2026-11"),
            view(
                id="c",
                filename="sop_GH-01.docx",
                owner="Ramp lead",
                owner_checked=True,
                controlled_copy=False,
                controlled_copy_set=True,
            ),
            view(id="d", filename="manual.pdf", kind="manual"),
            # The same SOP again, older: marked and left out of the counts.
            view(id="e", title="SOP LC-07", version_date="2019-04", filename="old.docx"),
            view(id="f", kind="job_description", filename="jd.docx"),
        ],
        roles,
        "2026-11-25",
    )
    by = {e.source_id: e for e in found}
    assert set(by) == {"a", "b", "c", "d", "e"}  # SOPs and manuals only
    assert (by["a"].owner, by["a"].owner_status, by["a"].updated_by) == (
        "Load control lead", "role", "Quality manager",
    )  # fmt: skip
    assert by["b"].owner_status == "check" and by["c"].owner_status == "other"
    assert by["d"].owner_status == "none"
    # Overdue only once the due date (to the end of its month) has passed.
    assert by["a"].overdue and not by["b"].overdue
    # A copy is uncontrolled only once Eric has said so; an old "no" is not known.
    assert [by[k].controlled for k in "abcd"] == [True, None, False, None]
    assert not by["a"].older  # "sop_LC-07" (file name) differs from the title "SOP LC-07"
    counts = sop_register.counts(found)
    assert counts == sop_register.Counts(sops=5, without_owner=2, without_updater=4, overdue=1,
                                         uncontrolled=1)  # fmt: skip


def test_the_newest_of_the_same_sop_counts_once() -> None:
    found = sop_register.entries(
        [
            view(id="old", title="LC-07 Load control", version_date="2019-04"),
            view(
                id="new",
                title="lc-07 load control",
                version_date="2024-02",
                filename="b.docx",
                review_due="2020-01",
            ),
        ],
        {},
        "2026-11-25",
    )
    assert [(e.source_id, e.older) for e in found] == [("old", True), ("new", False)]
    assert sop_register.counts(found).sops == 1
    assert sop_register.counts(found).overdue == 1


@pytest.fixture()
def built(
    settings_config: AppConfig,
) -> Iterator[tuple[TestClient, fixture_engagement.FixtureEngagement]]:
    for client in make_client(settings_config):
        yield client, fixture_engagement.build(client, SOP_FILES)


def test_the_register_through_the_api(
    built: tuple[TestClient, fixture_engagement.FixtureEngagement],
) -> None:
    client, eng = built
    lc07, rp02 = eng.sources["sop_LC-07.docx"], eng.sources["sop_RP-02.docx"]
    lead = eng.roles["Load control lead"]

    def patch(sid: str, body: dict[str, Any]) -> Any:
        return client.patch(f"/api/sources/{sid}", json=body)

    def register() -> dict[str, Any]:
        r = client.get(f"/api/engagements/{eng.engagement_id}/sop-register")
        assert r.status_code == 200, r.text
        return dict(r.json())

    first = register()
    assert first["counts"] == {"sops": 2, "without_owner": 2, "without_updater": 2,
                               "overdue": 0, "uncontrolled": 0}  # fmt: skip
    assert [e["title"] for e in first["entries"]] == ["sop_LC-07", "sop_RP-02"]

    ok = patch(lc07, {"owner_role_id": lead, "updated_by_other": "Quality office",
                      "last_reviewed": "2024-05", "review_due": "2025-05",
                      "controlled_copy": False, "title": "LC-07 Load control"})  # fmt: skip
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["owner_role_id"] == lead and body["owner"] == "Load control lead"
    assert body["owner_checked"] and body["controlled_copy_set"]
    after = register()
    assert after["counts"] == {"sops": 2, "without_owner": 1, "without_updater": 1,
                               "overdue": 1, "uncontrolled": 1}  # fmt: skip
    entry = next(e for e in after["entries"] if e["source_id"] == lc07)
    assert (entry["owner"], entry["owner_status"], entry["updated_by"], entry["controlled"]) == (
        "Load control lead", "role", "Quality office", False,
    )  # fmt: skip
    # "Not known" clears the flag again.
    assert patch(lc07, {"controlled_copy_known": False}).json()["controlled_copy_set"] is False
    assert register()["counts"]["uncontrolled"] == 0

    # Roles, not people: a name on the list of names to hide is refused, in plain words.
    assert client.post(f"/api/engagements/{eng.engagement_id}/redaction-terms",
                       json={"term": "Priya Nair", "replacement": "Load controller"}
                       ).status_code == 201  # fmt: skip
    for field in ("owner", "updated_by_other", "title"):
        refused = patch(rp02, {field: "Priya Nair"})
        assert refused.status_code == 422
        assert refused.json()["error"]["message"] == "Name the role, not the person."
    # Checked: roles of this engagement, dates, and SOP fields on SOPs and manuals only.
    assert patch(rp02, {"owner_role_id": "nobody"}).status_code == 422
    assert patch(rp02, {"review_due": "next year"}).status_code == 422
    jd = eng.sources["jd_load_controller.docx"]
    assert patch(jd, {"owner_role_id": lead}).status_code == 422
    # Typed text is another role's name; marking an old owner text as a role checks it.
    typed = patch(rp02, {"owner": "Ramp lead"}).json()
    assert typed["owner_checked"] and typed["owner_role_id"] is None
    # A role in use as an SOP owner can't be removed.
    removed = client.delete(f"/api/roles/{lead}")
    assert removed.status_code == 409
    assert "SOP" in removed.json()["error"]["message"]


def test_the_process_owner_in_the_scope(
    built: tuple[TestClient, fixture_engagement.FixtureEngagement],
) -> None:
    client, eng = built
    url = f"/api/engagements/{eng.engagement_id}"
    lead = eng.roles["Load control lead"]
    assert client.get(url).json()["process_owner"] == ""
    set_role = client.patch(url, json={"process_owner_role_id": lead})
    assert set_role.status_code == 200, set_role.text
    assert set_role.json()["process_owner"] == "Load control lead"
    other = client.patch(url, json={"process_owner_other": "Head of ground operations"}).json()
    assert (other["process_owner_role_id"], other["process_owner"]) == (
        None, "Head of ground operations",
    )  # fmt: skip
    assert client.patch(url, json={"process_owner_role_id": "nobody"}).status_code == 422
    assert client.post(f"{url}/redaction-terms",
                       json={"term": "Priya Nair", "replacement": "Load controller"}
                       ).status_code == 201  # fmt: skip
    refused = client.patch(url, json={"process_owner_other": "Priya Nair"})
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == "Name the role, not the person."
    cleared = client.patch(url, json={"process_owner_other": ""}).json()
    assert cleared["process_owner"] == ""


def test_a_version_date_may_be_a_month_or_a_year(
    built: tuple[TestClient, fixture_engagement.FixtureEngagement],
) -> None:
    """DECISIONS 112: as the Capability Compass writes them ("2019-04"), for every source."""
    client, eng = built
    sid = eng.sources["sop_LC-07.docx"]
    for date in ("2019-04", "2019", "2019-04-30", ""):
        r = client.patch(f"/api/sources/{sid}", json={"version_date": date})
        assert r.status_code == 200, r.text
        assert r.json()["version_date"] == date
    for bad in ("2019-13", "April 2019", "19-04", "2019-04-32"):
        r = client.patch(f"/api/sources/{sid}", json={"version_date": bad})
        assert r.status_code == 422, bad
        assert r.json()["error"]["details"]["field"] == "version_date"
