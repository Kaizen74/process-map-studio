"""Choosing the roles another flow brings along, and removing a role nothing uses (2026-10-31,
Eric: "Both", after the Export cargo Setup screen listed Load control's six roles; DECISIONS 93).
API_CONTRACT → POST /engagements/{id}/another-flow `role_ids`, DELETE /roles/{rid}. Mocked."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.actions.engagements import role_in_use
from app.db import session_scope
from app.domain.models import RoleUses
from app.repositories.tables import AuditRow
from tests.unit.test_another_flow import EXPORT, first, get
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted", "first"]


def roles(client: TestClient, eid: str) -> list[tuple[str, int]]:
    return [(r["name"], r["lane_order"]) for r in get(client, f"/api/engagements/{eid}/roles")]


def audit_actions(client: TestClient, eid: str) -> list[dict[str, Any]]:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = session.scalars(select(AuditRow).where(AuditRow.engagement_id == eid)).all()
        return [{"action": r.action, "before": r.before, "after": r.after} for r in rows]


def test_another_flow_brings_only_the_roles_ticked_numbered_from_the_top(
    first: tuple[TestClient, Any],
) -> None:
    client, built = first
    keep = [built.roles["Ramp"], built.roles["Captain"]]
    made = client.post(f"/api/engagements/{built.engagement_id}/another-flow",
                       json={**EXPORT, "role_ids": keep})  # fmt: skip
    assert made.status_code == 201, made.text
    new = made.json()["id"]
    assert roles(client, new) == [("Ramp", 1), ("Captain", 2)]
    # The interview's speaker was mapped to Load controller, left behind: copied unmapped.
    transcript = next(s for s in get(client, f"/api/engagements/{new}/sources")
                      if s["filename"] == "interview_transcript.txt")  # fmt: skip
    speakers = {s["label"]: s for s in get(client, f"/api/sources/{transcript['id']}/speakers")}
    assert speakers["Priya Nair"]["role_id"] is None
    [row] = [r for r in audit_actions(client, new)
             if r["action"] == "Started another flow from these sources"]  # fmt: skip
    assert row["after"]["roles"] == 2
    assert roles(client, built.engagement_id)[0] == ("Load controller", 1)  # first one untouched


def test_without_role_ids_every_role_comes_along_and_a_stranger_is_refused(
    first: tuple[TestClient, Any],
) -> None:
    client, built = first
    eid = built.engagement_id
    every = client.post(f"/api/engagements/{eid}/another-flow", json={**EXPORT, "role_ids": None})
    assert every.status_code == 201, every.text
    assert roles(client, every.json()["id"]) == roles(client, eid)
    none = client.post(f"/api/engagements/{eid}/another-flow",
                       json={**EXPORT, "name": "Import", "role_ids": []})  # fmt: skip
    assert none.status_code == 201 and roles(client, none.json()["id"]) == []
    stranger = {**EXPORT, "name": "Transfer", "role_ids": ["not-a-role"]}
    other = client.post(f"/api/engagements/{eid}/another-flow", json=stranger)
    assert other.status_code == 422
    assert other.json()["error"]["message"] == "Choose roles of this engagement."
    assert other.json()["error"]["details"]["field"] == "role_ids"


def test_a_role_nothing_uses_is_removed_and_the_lanes_close_up(
    first: tuple[TestClient, Any],
) -> None:
    client, built = first
    eid = built.engagement_id
    gone = client.delete(f"/api/roles/{built.roles['Load control lead']}")
    assert gone.status_code == 204, gone.text
    assert roles(client, eid) == [("Load controller", 1), ("Ramp", 2), ("Airline ops", 3),
                                  ("Captain", 4)]  # fmt: skip
    [row] = [r for r in audit_actions(client, eid) if r["action"] == "Removed role"]
    assert row["before"] == {"name": "Load control lead", "aliases": ["Load Control Lead"],
                             "is_system": False, "lane_order": 2}  # fmt: skip
    again = client.delete(f"/api/roles/{built.roles['Load control lead']}")
    assert again.status_code == 404
    assert again.json()["error"]["message"] == "That role doesn't exist. It may have been removed."


def test_a_role_a_speaker_is_mapped_to_stays_and_says_why(first: tuple[TestClient, Any]) -> None:
    client, built = first
    refused = client.delete(f"/api/roles/{built.roles['Load controller']}")
    assert refused.status_code == 409
    assert refused.json()["error"]["message"] == (
        "Load controller can't be removed: a speaker in an interview is mapped to it."
    )
    assert ("Load controller", 1) in roles(client, built.engagement_id)


def test_a_role_a_step_uses_stays_and_names_the_steps(drafted: Drafted) -> None:
    client = drafted.client
    lanes = {r["name"]: r["id"]
             for r in get(client, f"/api/engagements/{drafted.engagement_id}/roles")}  # fmt: skip
    refused = client.delete(f"/api/roles/{lanes['Load control lead']}")
    assert refused.status_code == 409
    assert refused.json()["error"]["message"] == (
        "Load control lead can't be removed: 2 steps use it (“Approve load plan”, "
        "“Deviation in limits?”)."
    )
    # A published version never changes, so its roles stay too.
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    assert client.delete(f"/api/roles/{lanes['Load control lead']}").status_code == 409


def test_the_reasons_read_as_one_sentence() -> None:
    one = RoleUses(steps=["Draft load plan"])
    assert role_in_use("Ramp", one) == "Ramp can't be removed: 1 step uses it (“Draft load plan”)."
    many = RoleUses(steps=["A", "B", "C", "D"], events=3, costs=1, intents=1, discrepancies=2,
                    profiles=1)  # fmt: skip
    assert role_in_use("Ramp", many) == (
        "Ramp can't be removed: 4 steps use it (“A”, “B” and 2 more); an interviewee profile "
        "names it; a system log's events are mapped to it; it has an hourly cost; an intent "
        "statement names it as owner; a discrepancy names it as decision owner."
    )
    assert role_in_use("Ramp", RoleUses()) == ""
