"""Review endpoints for the detail panel (API_CONTRACT.md → Review): one step with its evidence
cards, names and quotes; a source opened at a passage. Real database, Claude mocked, on the
illustrative Appendix A engagement."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, run_draft, with_key


@dataclass
class Drafted:
    client: TestClient
    graph: dict[str, Any]

    def element(self, label: str) -> dict[str, Any]:
        eid = next(e["id"] for e in self.graph["elements"] if e["label"] == label)
        response = self.client.get(f"/api/elements/{eid}")
        assert response.status_code == 200, response.text
        return dict(response.json())


@pytest.fixture()
def drafted(settings_config: AppConfig) -> Iterator[Drafted]:
    for client in make_client(settings_config):
        built = fixture_engagement.build(with_key(client))
        job = run_draft(client, built.engagement_id)
        graph = client.get(f"/api/versions/{job['target_id']}/graph").json()
        yield Drafted(client, graph)


def test_a_step_comes_with_names_quotes_and_source_names(drafted: Drafted) -> None:
    plan = drafted.element("Draft load plan")
    in_graph = next(e for e in drafted.graph["elements"] if e["label"] == "Draft load plan")
    shared = set(in_graph) - {"evidence", "raci"}
    assert {k: plan[k] for k in shared} == {k: in_graph[k] for k in shared}
    assert plan["version_id"] == drafted.graph["version"]["id"]
    assert (plan["lane_role_name"], plan["phase_name"]) == ("Load controller", "Plan")
    assert (plan["image_count"], plan["gap_findings"]) == (0, [])
    cards = plan["evidence"]
    # Same cards, same order as the graph, now with the file name and the quote.
    assert [(c["segment_id"], c["stance"], c["anchor"]) for c in cards] == [
        (e["segment_id"], e["stance"], e["anchor"]) for e in in_graph["evidence"]
    ]
    first = cards[0]
    assert (first["source_name"], first["stance"], first["anchor"]) == (
        "interview_transcript.txt", "supports", "06:40")  # fmt: skip
    assert first["quote"] and first["verified"]
    silent = [c for c in cards if c["stance"] == "silent"]
    assert silent and all(c["segment_id"] is None and c["quote"] == "" for c in silent)
    # The documents, and the landscape interview (A.10), which says nothing of drafting.
    assert {c["source_name"] for c in silent} == {
        "sop_RP-02.docx", "jd_load_control_lead.docx", "landscape_ramp_lead.txt",
    }  # fmt: skip
    assert [(r["role_name"], r["letter"]) for r in plan["raci"]] == [
        ("Load controller", "R"),
        ("Load controller", "A"),
    ]


def test_a_contested_accountable_role_names_its_competing_sources(drafted: Drafted) -> None:
    deviation = drafted.element("Deviation in limits?")
    assert deviation["decider_role_name"] == "Load controller"
    accountable = sorted(
        (r["role_name"], r["contested"], sorted({s["source_kind"] for s in r["sources"]}))
        for r in deviation["raci"]
        if r["letter"] == "A"
    )
    assert accountable == [
        ("Captain", True, ["interview_transcript"]),
        ("Load control lead", True, ["sop"]),
    ]
    assert all(s["anchor"] for r in deviation["raci"] for s in r["sources"])


def test_no_name_on_the_hidden_list_reaches_the_panel(drafted: Drafted) -> None:
    texts = [drafted.client.get(f"/api/elements/{e['id']}").text for e in drafted.graph["elements"]]
    assert all("Priya" not in t for t in texts)
    start = drafted.element("Flight scheduled")
    assert (start["evidence"], start["raci"], start["lane_role_name"]) == ([], [], "")


def test_a_missing_step_is_not_found(drafted: Drafted) -> None:
    response = drafted.client.get("/api/elements/nope")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "That step doesn't exist."


def test_a_source_opens_at_the_page_that_holds_a_passage(drafted: Drafted) -> None:
    card = next(c for c in drafted.element("Draft load plan")["evidence"] if c["segment_id"])
    source, segment = card["source_id"], card["segment_id"]
    everything = drafted.client.get(f"/api/sources/{source}/segments").json()
    position = [s["id"] for s in everything["segments"]].index(segment)
    page = drafted.client.get(
        f"/api/sources/{source}/segments", params={"around": segment, "page_size": 2}
    ).json()
    assert page["page"] == position // 2 + 1
    assert segment in [s["id"] for s in page["segments"]]
    other = next(
        c["source_id"]
        for c in drafted.element("Draft load plan")["evidence"]
        if c["source_id"] != source
    )
    elsewhere = drafted.client.get(f"/api/sources/{other}/segments", params={"around": segment})
    assert elsewhere.status_code == 404
    assert elsewhere.json()["error"]["message"] == "That passage isn't in this source."
