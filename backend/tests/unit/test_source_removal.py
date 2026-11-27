"""Deleting a source a draft was made from (DECISIONS 114; API_CONTRACT.md → Sources, Versions).

Eric deleted two SOPs after drafting from them and the draft quietly lost its evidence. The Sources
screen now says which versions were drafted from a file and how many steps are built from it before
he deletes it; afterwards the draft names the deleted files until it is refreshed."""

from __future__ import annotations

from typing import Any

from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_refresh import refresh

__all__ = ["drafted"]


def sources(d: Drafted) -> dict[str, dict[str, Any]]:
    response = d.client.get(f"/api/engagements/{d.engagement_id}/sources")
    assert response.status_code == 200, response.text
    return {s["filename"]: s for s in response.json()}


def removed(d: Drafted) -> list[str]:
    response = d.client.get(f"/api/versions/{d.version_id}")
    assert response.status_code == 200, response.text
    return list(response.json()["removed_sources"])


def test_a_source_says_which_versions_and_steps_use_it(drafted: Drafted) -> None:
    found = sources(drafted)
    sop = found["sop_LC-07.docx"]
    assert sop["used_by"] == ["v0.1 (draft)"]
    assert sop["steps_citing"] > 0
    one = drafted.client.get(f"/api/sources/{sop['id']}").json()
    assert (one["used_by"], one["steps_citing"]) == (sop["used_by"], sop["steps_citing"])
    assert removed(drafted) == []


def test_deleting_a_source_marks_the_draft_until_it_is_refreshed(drafted: Drafted) -> None:
    sop = sources(drafted)["sop_LC-07.docx"]
    assert drafted.client.delete(f"/api/sources/{sop['id']}").status_code == 204
    assert removed(drafted) == ["sop_LC-07.docx"]
    job = refresh(drafted)
    assert job["status"] == "done", job
    assert removed(drafted) == []  # rebuilt from the sources there are now


def test_a_source_added_after_the_draft_is_used_by_nothing(drafted: Drafted) -> None:
    from tests.uploads import upload, wait_for_jobs

    upload(drafted.client, drafted.engagement_id, "sop_RP-02.docx")
    wait_for_jobs(drafted.client)
    found = sources(drafted)
    late = [s for name, s in found.items() if name == "sop_RP-02.docx" and not s["used_by"]]
    assert late and late[-1]["steps_citing"] == 0
