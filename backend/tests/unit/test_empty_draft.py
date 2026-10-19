"""A draft from which nothing could be drafted (Eric, 2026-10-19: "a draft with no steps should
still show a start and an end on its map"). The start and end come from the scope card, as on
every map; no line joins them, because no source describes what happens in between (constraint
23: gaps are never filled). Eric can then add the steps himself on Review."""

from __future__ import annotations

from app.config import AppConfig
from tests.golden.test_golden_baselines import drafted

# Claude is mocked by exactly what is sent, and no answers were recorded for this mix: every
# stage answers with nothing, so nothing can be drafted.
NOTHING_RECORDED = ["interview_transcript.txt", "sop_LC-07.docx"]


def test_an_empty_draft_still_has_its_start_and_end(settings_config: AppConfig) -> None:
    for client, version_id in drafted(settings_config, NOTHING_RECORDED):
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        found = sorted((e["kind"], e["label"], e["provenance"]) for e in graph["elements"])
        assert found == [("end", "Final load sheet issued", "O"),
                         ("start", "Flight scheduled", "O")]  # fmt: skip
        assert graph["edges"] == []
        engagement_id = client.get(f"/api/versions/{version_id}").json()["engagement_id"]
        draft = client.get(f"/api/engagements/{engagement_id}/draft").json()
        assert draft["summary"]["steps"] == 0
        # The map checks say what is missing, in plain words.
        failures = client.get(f"/api/versions/{version_id}/lint").json()["failures"]
        assert 'Start "Flight scheduled" has no way out (no outgoing connection).' in {
            f["message"] for f in failures
        }
        # The map can be drawn, in both views.
        layout = client.get(f"/api/versions/{version_id}/layout")
        assert layout.status_code == 200, layout.text
        assert {n["id"] for n in layout.json()["nodes"]} == {e["id"] for e in graph["elements"]}
        for view in ("done", "documented"):
            seen = client.get(f"/api/versions/{version_id}/graph?view={view}").json()
            assert sorted(e["kind"] for e in seen["elements"]) == ["end", "start"], view


def test_eric_can_build_the_map_from_an_empty_draft(settings_config: AppConfig) -> None:
    """He adds a step after the start, from a passage, and draws the line on to the end."""
    for client, version_id in drafted(settings_config, NOTHING_RECORDED):
        graph = client.get(f"/api/versions/{version_id}/graph").json()
        ids = {e["kind"]: e["id"] for e in graph["elements"]}
        engagement_id = client.get(f"/api/versions/{version_id}").json()["engagement_id"]
        listed = client.get(f"/api/engagements/{engagement_id}/roles").json()
        roles = {r["name"]: r["id"] for r in listed}
        sources = client.get(f"/api/engagements/{engagement_id}/sources").json()
        sop = next(s["id"] for s in sources if s["filename"] == "sop_LC-07.docx")
        segment = client.get(f"/api/sources/{sop}/segments").json()["segments"][0]["id"]
        added = client.post(f"/api/versions/{version_id}/elements", json={
            "kind": "activity", "label": "Draft load plan", "provenance": "O",
            "lane_role_id": roles["Load controller"], "after_element_id": ids["start"],
            "segment_ids": [segment]})  # fmt: skip
        assert added.status_code == 201, added.text
        step = added.json()["id"]
        to_end = {"from": step, "to": ids["end"], "kind": "sequence", "label": ""}
        line = client.post(f"/api/versions/{version_id}/edges", json=to_end)
        assert line.status_code == 201, line.text
        edges = client.get(f"/api/versions/{version_id}/graph").json()["edges"]
        assert {(e["from"], e["to"]) for e in edges} == {(ids["start"], step), (step, ids["end"])}
