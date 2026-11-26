"""Ready to send to the Capability Compass, and steps citing no SOP or manual (DECISIONS 113), on
the Belmar fixture: fixed rules, read only, never a block on the download."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.accountability_fixture import CM, Fixture, build
from tests.unit.test_acceptance_accountability import compare_and_class, set_register
from tests.unit.test_compass_handoff import client as client  # the shared fixture


@pytest.fixture()
def fx(client: TestClient) -> Iterator[Fixture]:
    yield build(client)


def lines(fx: Fixture) -> dict[str, dict[str, Any]]:
    b = fx.belmar
    body = b.get(f"/api/versions/{b.version_id}/compass-readiness")
    assert (body["version_label"], body["state"]) == ("v1.0", "published")
    return {i["key"]: i for i in body["items"]}


def test_what_each_question_still_lacks(fx: Fixture) -> None:
    found = lines(fx)
    assert [k for k in found] == ["on_paper", "systems", "data_moves", "times", "sop_owners",
                                  "uncited", "process_owner"]  # fmt: skip
    assert found["on_paper"]["text"] == (
        "Decider named in the documents: recorded on 2 of 4 decisions and approvals"
    )
    assert (found["on_paper"]["complete"], found["on_paper"]["screen"]) == (False, "review")
    assert found["systems"]["text"] == "System of record: recorded on 9 of 11 steps"
    assert found["data_moves"]["text"] == "How data moves: recorded on 6 of 6 handoffs"
    assert found["data_moves"]["complete"] is True
    assert found["times"]["complete"] is True
    assert found["sop_owners"]["text"] == (
        "SOP owners and updaters: both recorded for 0 of 2 SOPs and manuals"
    )
    assert found["uncited"]["text"] == "Steps citing no SOP or manual: 2 of 11"
    assert found["uncited"]["complete"] is None  # to read, not to fill
    assert found["process_owner"]["text"] == "Process owner: not named"
    # The download is never blocked by any of it.
    b = fx.belmar
    assert b.client.get(f"/api/versions/{b.version_id}/compass-return").status_code == 200


def test_lines_close_as_eric_records_them(fx: Fixture) -> None:
    b = fx.belmar
    set_register(b)
    b.client.patch(f"/api/engagements/{b.engagement_id}",
                   json={"process_owner_role_id": b.roles[CM]})  # fmt: skip
    found = lines(fx)
    assert found["sop_owners"]["text"].startswith(
        "SOP owners and updaters: both recorded for 1 of 2"
    )
    assert found["process_owner"] == {
        "key": "process_owner", "text": "Process owner: Country manager", "done": None,
        "total": None, "complete": True, "screen": "setup",
    }  # fmt: skip
    # A comparison where Belmar is the other unit: complete once every difference is decided,
    # open again when one is reopened.
    view = compare_and_class(fx)
    assert lines(fx)["differences"] == {
        "key": "differences", "text": "Differences from Arden: 0 not classed or kept yet",
        "done": None, "total": None, "complete": True, "screen": "compare",
    }  # fmt: skip
    key = view["differences"][0]["key"]
    reopened = fx.client.put(f"/api/comparisons/{view['id']}/differences/{key}",
                             json={"action": "reopen"})  # fmt: skip
    assert reopened.status_code == 200, reopened.text
    assert lines(fx)["differences"]["text"] == "Differences from Arden: 1 not classed or kept yet"


def test_the_sources_screen_counts_steps_citing_no_sop(fx: Fixture) -> None:
    b = fx.belmar
    register = b.get(f"/api/engagements/{b.engagement_id}/sop-register")
    assert {k: register["map"][k] for k in ("version_label", "steps", "uncited")} == {
        "version_label": "v1.0", "steps": 11, "uncited": 2,
    }  # fmt: skip
    assert set(register["map"]["uncited_ids"]) == {b.steps["S-08"], b.steps["S-10"]}
