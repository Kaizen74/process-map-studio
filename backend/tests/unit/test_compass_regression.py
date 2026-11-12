"""Mock regression for the shared language with the other apps (2026-11-12, Eric's brief:
"conclude with mock test … no regression … the app can be used as a standalone"; DECISIONS 95-97).

Three journeys through the real routes, with every AI call mocked:
1. the sample hand-off: preview, start, test, draft, grade, publish, return file;
2. the three broken copies the brief names: refused in plain words, nothing created;
3. no hand-off at all: the same map, checks and downloads as before, with nothing of Compass.

The hand-off journey's map is the Appendix A sample (the mocked draft is written for its roles),
linked to the hand-off the way an engagement started from pilot VS-01 is.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.services import grade
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_compass_handoff import handoff, message, preview, start
from tests.unit.test_compass_return import download, link_to_handoff
from tests.unit.test_gap_decisions_api import decide_all_internal
from tests.unit.test_gap_system_findings_api import analyse
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

STANDALONE_KEYS = ("engagement_key", "pilot_ref")


def graph_of(d: Drafted) -> dict[str, Any]:
    return dict(d.client.get(f"/api/versions/{d.version_id}/graph").json())


def test_journey_1_the_sample_hand_off_from_preview_to_return_file(drafted: Drafted) -> None:
    client = drafted.client
    # Preview applies nothing; the pilot's IDs come back exactly as the file has them.
    before = len(client.get("/api/engagements").json())
    found = preview(client, handoff())
    assert found.status_code == 200, found.text
    assert len(client.get("/api/engagements").json()) == before
    pilot = next(p for p in found.json()["pilots"] if p["ref"] == "VS-01")
    assert pilot["cluster_ref"] == "CAP-04"
    link = link_to_handoff(drafted)  # an engagement started from VS-01, and its link
    assert (link["key"], link["pilot_ref"], link["cluster_ref"]) == ("MERIDIAN", "VS-01", "CAP-04")
    # The map carries the key, the pilot and a code on every step.
    graph = graph_of(drafted)
    assert (graph["process"]["engagement_key"], graph["process"]["pilot_ref"]) == (
        "MERIDIAN", "VS-01")  # fmt: skip
    codes = [e["code"] for e in graph["elements"] if e["kind"] not in ("start", "end")]
    assert codes == [f"S-{n:02d}" for n in range(1, len(codes) + 1)]
    # What is being tested, with a verdict resting on a step code.
    eid = drafted.engagement_id
    added = client.post(f"/api/engagements/{eid}/testing",
                        json={"ref": "H1", "text": "The paper report causes the wait.",
                              "refuted_by": "Waits without a paper report."})  # fmt: skip
    assert added.status_code == 201, added.text
    assert client.patch(f"/api/testing/{added.json()['id']}",
                        json={"verdict": "supported", "evidence_refs": [codes[4]]}
                        ).status_code == 200  # fmt: skip
    # Every gap finding is graded; the grade moves nothing else.
    report = analyse(drafted)
    assert report["findings"] and all(f["grade"]["grade"] in grade.GRADES
                                      for f in report["findings"])  # fmt: skip
    decide_all_internal(drafted, report)
    assert graph_of(drafted)["elements"] == graph["elements"]
    # Publish: the quality card is still what decides, and the codes are the same afterwards.
    assert download(drafted).status_code == 409  # not from a draft
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    after = [e["code"] for e in graph_of(drafted)["elements"] if e["kind"] not in ("start", "end")]
    assert after == codes
    for fmt in ("md", "json", "csv", "html"):
        assert client.get(f"/api/versions/{drafted.version_id}/export/{fmt}").status_code == 200
    file = download(drafted).json()
    assert (file["format"], file["engagement_key"]) == ("compass-return", "MERIDIAN")
    kinds = {f["kind"] for f in file["findings"]}
    assert {"step", "knowledge_risk", "hypothesis_verdict"} <= kinds
    assert {f["ref"] for f in file["findings"] if f["kind"] == "step"} == set(codes)
    [verdict] = [f for f in file["findings"] if f["kind"] == "hypothesis_verdict"]
    assert (verdict["ref"], verdict["relates_to"]) == ("H1", ["VS-01", "CAP-04"])
    assert download(drafted, fmt="md").status_code == 200


def test_journey_2_the_three_broken_copies_are_refused_and_nothing_is_created(
    client: TestClient,
) -> None:
    wrong_format = handoff()
    wrong_format["format"] = "something-else"
    no_key = handoff()
    del no_key["engagement"]["key"]
    cluster_nowhere = handoff()
    for pilot in cluster_nowhere["pilots"]:
        pilot["cluster_ref"] = "CAP-99"
    said = {
        "format": message(preview(client, wrong_format)),
        "key": message(preview(client, no_key)),
        "cluster": message(preview(client, cluster_nowhere)),
    }
    assert said["format"].startswith("This isn't a Capability Compass hand-off file")
    assert said["key"].startswith("This hand-off has no engagement key")
    assert "points to cluster CAP-99, which isn't in this file" in said["cluster"]
    for text in said.values():  # plain language: no code names, no traceback
        assert "Traceback" not in text and "KeyError" not in text and "{" not in text
    for broken in (wrong_format, no_key, cluster_nowhere):
        assert preview(client, broken).status_code == 422
        body = {"name": "Should not exist", "compass": {"handoff": broken, "pilot_ref": "VS-01"}}
        made = client.post("/api/engagements", json=body)
        assert made.status_code == 422, made.text
    assert client.get("/api/engagements").json() == []
    # The good file still works straight afterwards.
    assert start(client).status_code == 201


def test_journey_3_without_a_hand_off_the_app_is_whole(drafted: Drafted) -> None:
    client = drafted.client
    eid = drafted.engagement_id
    engagement = client.get(f"/api/engagements/{eid}").json()
    assert engagement["compass"] is None
    assert client.get(f"/api/engagements/{eid}/testing").json() == []
    graph = graph_of(drafted)
    assert [graph["process"][k] for k in STANDALONE_KEYS] == [None, None]
    # Codes and grades are the app's own: they need no hand-off.
    assert all(e["code"] for e in graph["elements"] if e["kind"] not in ("start", "end"))
    report = analyse(drafted)
    assert all(f["grade"]["grade"] in grade.GRADES for f in report["findings"])
    # What we are testing works standalone too: Eric's own hypotheses.
    own = client.post(f"/api/engagements/{eid}/testing",
                      json={"ref": "H1", "text": "Late notices drive the rework.",
                            "refuted_by": "Rework without a late notice."})  # fmt: skip
    assert own.status_code == 201, own.text
    decide_all_internal(drafted, report)
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    card = client.get(f"/api/versions/{drafted.version_id}/quality-card").json()
    assert card["all_green"] is True
    for fmt in ("md", "json", "csv", "html"):
        export = client.get(f"/api/versions/{drafted.version_id}/export/{fmt}")
        assert export.status_code == 200, export.text
        assert "MERIDIAN" not in export.text and "Engagement key" not in export.text
    refused = download(drafted)
    assert refused.status_code == 409
    assert "didn't start from a Capability Compass" in refused.json()["error"]["message"]
