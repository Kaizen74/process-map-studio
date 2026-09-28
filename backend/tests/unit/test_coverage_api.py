"""Coverage (PRD §3.8 G11; API_CONTRACT.md → GET /api/sources/{sid}/segments) on the illustrative
Appendix A engagement, Claude mocked: the share of each source's passages that a verified claim
of the current map cites, interviewer turns left out; the passages nothing cites, on request."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update

from app.config import AppConfig
from app.db import session_scope
from app.repositories.tables import Claim
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, with_key
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import upload, wait_for_jobs

__all__ = ["drafted"]

TRANSCRIPT, SOP = "interview_transcript.txt", "sop_LC-07.docx"


def sources(d: Drafted) -> dict[str, dict[str, Any]]:
    listed = d.client.get(f"/api/engagements/{d.engagement_id}/sources").json()
    return {s["filename"]: s for s in listed}


def passages(d: Drafted, name: str, **query: str) -> dict[str, Any]:
    source_id = sources(d)[name]["id"]
    response = d.client.get(f"/api/sources/{source_id}/segments", params=query)
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_no_coverage_before_a_draft(settings_config: AppConfig) -> None:
    for client in make_client(settings_config):
        built = fixture_engagement.build(with_key(client))
        listed = client.get(f"/api/engagements/{built.engagement_id}/sources").json()
        assert {s["coverage_pct"] for s in listed} == {None}
        page = client.get(f"/api/sources/{built.sources[SOP]}/segments").json()
        assert page["coverage_pct"] is None
        assert not any(s["cited"] for s in page["segments"])


def test_coverage_is_the_share_of_passages_verified_claims_cite(drafted: Drafted) -> None:
    listed = sources(drafted)
    for name, source in listed.items():
        page = passages(drafted, name)
        assert source["coverage_pct"] == page["coverage_pct"]  # the registry and the viewer agree
        counted = [s for s in page["segments"] if s["speaker_role"] != "Interviewer"]
        cited = [s for s in counted if s["cited"]]
        assert page["coverage_pct"] == round(100 * len(cited) / len(counted), 1), name
    # The interview is fully used once the interviewer's questions are left out; the SOP half.
    assert (listed[TRANSCRIPT]["coverage_pct"], listed[SOP]["coverage_pct"]) == (100.0, 50.0)
    assert drafted.client.get(f"/api/sources/{listed[SOP]['id']}").json()["coverage_pct"] == 50.0


def test_uncited_only_lists_what_nothing_cites(drafted: Drafted) -> None:
    everything = passages(drafted, SOP)["segments"]
    uncited = passages(drafted, SOP, uncited_only="1")
    assert [s["id"] for s in uncited["segments"]] == [s["id"] for s in everything if not s["cited"]]
    assert uncited["total"] == 5 and uncited["pages"] == 1
    # Interviewer turns are never listed as skipped, even if uncited.
    interview = passages(drafted, TRANSCRIPT, uncited_only="1")
    assert interview["segments"] == [] and interview["total"] == 0
    cited = next(s for s in everything if s["cited"])
    both = drafted.client.get(
        f"/api/sources/{sources(drafted)[SOP]['id']}/segments",
        params={"uncited_only": "1", "around": cited["id"]},
    )
    assert both.status_code == 422
    assert both.json()["error"]["details"]["field"] == "uncited_only"


def test_only_verified_claims_count(drafted: Drafted) -> None:
    before = sources(drafted)[SOP]["coverage_pct"]
    with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        session.execute(update(Claim).values(verification_status="rejected"))
    after = sources(drafted)
    assert before == 50.0 and after[SOP]["coverage_pct"] == 0.0
    assert not any(s["cited"] for s in passages(drafted, SOP)["segments"])


def test_a_source_added_after_the_draft_has_no_coverage_yet(drafted: Drafted) -> None:
    assert upload(drafted.client, drafted.engagement_id, "manual_extract.pdf").status_code == 201
    wait_for_jobs(drafted.client)
    assert sources(drafted)["manual_extract.pdf"]["coverage_pct"] is None


def test_a_reopened_draft_keeps_the_coverage_of_its_version(drafted: Drafted) -> None:
    before = {name: s["coverage_pct"] for name, s in sources(drafted).items()}
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    assert {name: s["coverage_pct"] for name, s in sources(drafted).items()} == before
    reopened = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen")
    assert reopened.status_code == 201, reopened.text
    assert {name: s["coverage_pct"] for name, s in sources(drafted).items()} == before
