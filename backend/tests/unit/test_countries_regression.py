"""Mock regression for "the same process in another country" (2026-11-13, Eric's brief §7;
DECISIONS 98): one journey through the real routes that walks the brief's acceptance tests in
order, and the app on its own with no packet and no comparison. Claude is mocked throughout.

1 Belmar starts from Arden's scope card, conventions and lanes, and nothing else crosses.
2 Both show their country; both carry pilot VS-01.
3 The obvious steps are proposed; confirmed pairs survive a republish.
4 Different deciders give a decision_right difference; a step only Arden has is "Only in Arden";
  a time difference under 1.5 times gives nothing.
5 Classing gives V1, then V2; dismissing and classing again never reuses a code.
6 Belmar's return file has its country and variations; Arden's has none.
7 The printable pages hold no name, quote or source text (the browser check prints them).
8 A draft, and a map of a different process, are refused in plain words.
9 Everything else keeps working: the other tests and checks run with this one.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.db import session_scope
from app.repositories.tables import Source
from tests.countries_fixture import PERSON, build, republish
from tests.unit.test_comparisons_api import (
    APPROVE,
    DRAFT_PRICE,
    LEGAL,
    RECEIVE,
    by_kind,
    confirm_proposals,
    decide_pair,
)
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.uploads import wait_for_jobs


def sources_of(client: TestClient, engagement_id: str) -> list[str]:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        return [s.filename for s in session.query(Source).filter_by(engagement_id=engagement_id)]


def test_the_brief_end_to_end(client: TestClient) -> None:
    c = build(client)
    arden, belmar = c.get(f"/api/engagements/{c.arden}"), c.get(f"/api/engagements/{c.belmar}")
    # 1 and 2
    assert (belmar["reference_engagement_id"], belmar["process_name"]) == (
        c.arden,
        arden["process_name"],
    )
    assert sources_of(client, c.belmar) == [
        "interview_belmar_pricing.txt",
        "sop_belmar_renewals.docx",
    ]  # its own, written by the fixture after it started; none of Arden's
    assert (arden["country"], belmar["country"]) == ("Arden", "Belmar")
    assert arden["compass"]["pilot_ref"] == belmar["compass"]["pilot_ref"] == "VS-01"
    # 8: a different process and a draft are refused
    alone = client.post("/api/engagements", json={"name": "Load control"}).json()
    other = client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": alone["id"]},
    )
    assert other.status_code == 409 and "different processes" in other.json()["error"]["message"]
    draft = client.post(f"/api/versions/{c.arden_version}/reopen").json()
    refused = client.post(
        "/api/comparisons",
        json={
            "reference_engagement_id": c.arden,
            "other_engagement_id": c.belmar,
            "reference_version_id": draft["id"],
        },
    )
    assert refused.status_code == 409 and "is a draft" in refused.json()["error"]["message"]
    # 3: proposals, Claude's (mocked) suggestion, Eric's decisions
    made = client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": c.belmar},
    )
    view = confirm_proposals(c, made.json())
    started = client.post(f"/api/comparisons/{view['id']}/suggest").json()
    wait_for_jobs(client)
    assert c.get(f"/api/jobs/{started['job_id']}")["status"] == "done"
    view = decide_pair(c, view["id"], LEGAL, None, "only_reference")
    view = decide_pair(c, view["id"], None, "check-the-credit-limit", "only_other")
    republish(client, c.belmar, c.belmar_version)
    view = client.post(f"/api/comparisons/{view['id']}/refresh").json()
    found = by_kind(view)
    # 4
    assert found[("who_decides", APPROVE, APPROVE)]["topic"] == "decision_right"
    assert ("only_reference", LEGAL, None) in found
    assert not [k for k in found if RECEIVE in (k[1], k[2])]
    assert ("work_time", DRAFT_PRICE, DRAFT_PRICE) in found

    # 5
    def act(key: str, **body: Any) -> Any:
        return client.put(f"/api/comparisons/{view['id']}/differences/{key}", json=body).json()

    v1 = act(
        found[("who_decides", APPROVE, APPROVE)]["key"],
        action="class",
        reason_class="inherited",
        reason_note="Pre-merger delegation of authority.",
    )
    v2 = act(found[("work_time", DRAFT_PRICE, DRAFT_PRICE)]["key"], action="keep")
    gone = act(found[("who_does", APPROVE, APPROVE)]["key"], action="dismiss", note="Same as V1.")
    v3 = act(found[("only_reference", LEGAL, None)]["key"], action="class", reason_class="unknown")
    assert [v1["code"], v2["code"], gone["code"], v3["code"]] == ["V1", "V2", None, "V3"]
    # 6
    latest = view["other"]["version_id"]
    belmar_file = c.get(f"/api/versions/{latest}/compass-return")
    arden_file = c.get(f"/api/versions/{c.arden_version}/compass-return")
    assert belmar_file["country"] == "Belmar" and arden_file["country"] == "Arden"
    assert [f["ref"] for f in belmar_file["findings"] if f["kind"] == "variation"] == [
        "V1",
        "V2",
        "V3",
    ]
    assert not [f for f in arden_file["findings"] if f["kind"] == "variation"]
    # 7
    pages = client.get(f"/api/comparisons/{view['id']}/export?layout=a3")
    assert pages.status_code == 200
    assert not [p for p in PERSON.values() if p in pages.text] and "said the" not in pages.text


def test_with_no_packet_and_no_comparison_the_app_works_as_before(client: TestClient) -> None:
    made = client.post("/api/engagements", json={"name": "Load control"})
    assert made.status_code == 201
    body = made.json()
    assert (body["country"], body["reference_engagement_id"], body["compass"]) == ("", None, None)
    eid = body["id"]
    assert client.get(f"/api/engagements/{eid}/comparison-candidates").json() == []
    assert client.get(f"/api/engagements/{eid}/comparisons").json() == []
    assert client.get(f"/api/engagements/{eid}/readiness").status_code == 200
    assert client.get("/api/comparisons/nope").status_code == 404
