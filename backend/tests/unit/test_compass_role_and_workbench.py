"""Batch 2 of the four-app review (DECISIONS 113) on the Belmar fixture: a lane linked to its
Capability Compass role, what checks the data at a handoff, and the Workbench step file."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.accountability_fixture import CM, PERSON, SS, Fixture, build
from tests.unit.test_compass_handoff import client as client  # the shared fixture


@pytest.fixture()
def fx(client: TestClient) -> Iterator[Fixture]:
    yield build(client)


def link(fx: Fixture, role: str, ref: str | None) -> Any:
    b = fx.belmar
    return b.client.patch(f"/api/roles/{b.roles[role]}", json={"compass_role_ref": ref})


def test_a_lane_names_its_compass_role_and_step_findings_carry_it(fx: Fixture) -> None:
    b = fx.belmar
    engagement = b.get(f"/api/engagements/{b.engagement_id}")
    offered = [r["ref"] for r in engagement["compass"]["roles"]]
    assert offered and offered[0].startswith("RL-")
    done = link(fx, SS, offered[0])
    assert done.status_code == 200, done.text
    assert done.json()["compass_role_ref"] == offered[0]
    refused = link(fx, CM, "RL-999")
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == (
        "Choose one of the roles in the Capability Compass hand-off."
    )
    graph = b.get(f"/api/versions/{b.version_id}/graph")
    lane = next(r for r in graph["roles"] if r["id"] == b.roles[SS])
    assert lane["compass_role_ref"] == offered[0]
    file = b.get(f"/api/versions/{b.version_id}/compass-return")
    found = {f["ref"]: f for f in file["findings"] if f["kind"] == "step"}
    assert found["S-02"]["relates_to"] == ["VS-01", "CAP-04", offered[0]]  # Shift supervisor lane
    assert found["S-01"]["relates_to"] == ["VS-01", "CAP-04"]  # not linked
    assert link(fx, SS, None).json()["compass_role_ref"] is None


def test_what_checks_the_data_at_a_handoff(fx: Fixture) -> None:
    b, c = fx.belmar, fx.client
    draft = c.post(f"/api/versions/{b.version_id}/reopen").json()
    graph = c.get(f"/api/versions/{draft['id']}/graph").json()
    code = {e["id"]: e["code"] for e in graph["elements"]}
    line = next(
        x for x in graph["edges"] if (code.get(x["from"]), code.get(x["to"])) == ("S-01", "S-02")
    )
    url = f"/api/versions/{draft['id']}/edges/{line['id']}/data-move"
    sent = c.put(url, json={"check": "  Weight checked against the  booking  "})
    assert sent.status_code == 200, sent.text
    assert (sent.json()["data_check"], sent.json()["data_move"]) == (
        "Weight checked against the booking",
        "re_keyed",
    )  # fmt: skip  (the move is left as it was)
    assert c.put(url, json={"check": "x" * 201}).status_code == 422
    refused = c.put(url, json={"check": f"{PERSON['belmar']} checks it"})
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == "Name the role, not the person."
    moved = c.put(url, json={"data_move": "system_interface"}).json()
    assert (moved["data_move"], moved["data_check"]) == (
        "system_interface", "Weight checked against the booking",
    )  # fmt: skip
    again = c.get(f"/api/versions/{draft['id']}/graph").json()
    assert next(x for x in again["edges"] if x["id"] == line["id"])["data_check"] == (
        "Weight checked against the booking"
    )


def green_card(b: Any) -> None:
    """The fixture's map is written as published; its quality card is stamped green here (the
    card's own rules are tested with the sample engagement)."""
    from app.db import session_scope
    from app.repositories import versions as versions_repo

    card = {"checks": [], "warnings": [], "all_green": True}
    with session_scope(b.client.app.state.sessions) as s:
        versions_repo.set_quality_card(s, b.version_id, card)


def test_the_workbench_step_file(fx: Fixture) -> None:
    b = fx.belmar
    green_card(b)
    offered = b.get(f"/api/engagements/{b.engagement_id}")["compass"]["roles"][0]["ref"]
    link(fx, SS, offered)
    response = b.client.get(f"/api/versions/{b.version_id}/export/workbench")
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].endswith('-v1-0-workbench-steps.csv"')
    text = response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["Step code"] for r in rows] == [f"S-{n:02d}" for n in range(1, 12)]
    s02 = rows[1]
    assert {k: s02[k] for k in ("Engagement key", "Pilot", "Step", "Lane role", "Compass role",
                                "Work min", "Wait min", "System of record")} == {
        "Engagement key": "MERIDIANBE", "Pilot": "VS-01", "Step": "Weigh the cargo",
        "Lane role": SS, "Compass role": offered, "Work min": "60", "Wait min": "0",
        "System of record": "Load control system",
    }  # fmt: skip
    assert rows[0]["System of record"] == "none: paper or memory"
    assert rows[2]["Rule or judgment"] == "judgment"
    assert PERSON["belmar"] not in text
