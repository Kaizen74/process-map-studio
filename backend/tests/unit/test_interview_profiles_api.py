"""Interviewee profiles (API_CONTRACT.md → Interviewee profiles; PRD Appendix F.8 rule 1, C5a):
roles or stakeholder groups only, never people (constraint 10), every change audited."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import AppConfig
from app.db import session_scope
from app.main import create_app
from app.repositories.tables import AuditRow


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


@pytest.fixture()
def engagement(client: TestClient) -> dict[str, Any]:
    created = client.post("/api/engagements", json={"name": "Load control"}).json()
    roles = {}
    for name in ("Load controller", "Ramp agent"):
        role = client.post(f"/api/engagements/{created['id']}/roles", json={"name": name}).json()
        roles[name] = role["id"]
    client.post(f"/api/engagements/{created['id']}/redaction-terms", json={"term": "Priya"})
    return {"id": created["id"], "roles": roles}


def url(engagement: dict[str, Any]) -> str:
    return f"/api/engagements/{engagement['id']}/profiles"


def audit_actions(client: TestClient, engagement_id: str) -> list[str]:
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        rows = session.scalars(
            select(AuditRow)
            .where(AuditRow.engagement_id == engagement_id, AuditRow.target_type == "profile")
            .order_by(AuditRow.created_at)
        )
        return [r.action for r in rows]


def test_profiles_are_added_listed_and_edited_with_audit_rows(
    client: TestClient, engagement: dict[str, Any]
) -> None:
    first = client.post(url(engagement), json={
        "role_id": engagement["roles"]["Ramp agent"], "stakeholder_group": " Ramp ",
        "interview_type": "landscape", "referred_by_role": "Load controller",
    })  # fmt: skip
    assert first.status_code == 201, first.text
    body = first.json()
    assert (body["role_name"], body["stakeholder_group"], body["interview_type"]) == (
        "Ramp agent", "Ramp", "landscape")  # fmt: skip
    assert body["previous_profile_id"] is None
    follow_up = client.post(url(engagement), json={
        "stakeholder_group": "Ramp", "interview_type": "follow_up",
        "previous_profile_id": body["id"],
    }).json()  # fmt: skip
    assert follow_up["role_id"] is None and follow_up["previous_profile_id"] == body["id"]
    listed = client.get(url(engagement)).json()
    assert [p["id"] for p in listed] == [body["id"], follow_up["id"]]  # oldest first

    edited = client.patch(f"/api/profiles/{body['id']}", json={"interview_type": "practice"})
    assert edited.status_code == 200 and edited.json()["interview_type"] == "practice"
    assert edited.json()["stakeholder_group"] == "Ramp"  # not sent, unchanged
    same = client.patch(f"/api/profiles/{body['id']}", json={"interview_type": "practice"})
    assert same.status_code == 200
    added, edited_row = "Added interviewee profile", "Edited interviewee profile"
    assert audit_actions(client, engagement["id"]) == [added, added, edited_row]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"interview_type": "chat", "stakeholder_group": "Ramp"}, "interview_type"),
        ({"interview_type": "practice"}, "role_id"),  # neither a role nor a group
        ({"interview_type": "practice", "role_id": "nope"}, "role_id"),
        ({"interview_type": "practice", "stakeholder_group": "x" * 121}, "stakeholder_group"),
        ({"interview_type": "practice", "stakeholder_group": "a\nb"}, "stakeholder_group"),
        ({"interview_type": "practice", "stakeholder_group": "Priya's team"}, "stakeholder_group"),
        ({"interview_type": "practice", "stakeholder_group": "Ramp",
          "referred_by_role": "priya"}, "referred_by_role"),
        ({"interview_type": "practice", "stakeholder_group": "Ramp",
          "previous_profile_id": "nope"}, "previous_profile_id"),
    ],
)  # fmt: skip
def test_the_rules_name_the_field(
    client: TestClient, engagement: dict[str, Any], body: dict[str, Any], field: str
) -> None:
    response = client.post(url(engagement), json=body)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["details"]["field"] == field
    assert "Priya" not in error["message"] and "priya" not in error["message"]  # never echoed
    assert client.get(url(engagement)).json() == []


def test_a_profile_cant_follow_itself_or_another_engagements_profile(
    client: TestClient, engagement: dict[str, Any]
) -> None:
    mine = client.post(url(engagement), json={"stakeholder_group": "Ramp",
                                              "interview_type": "practice"}).json()  # fmt: skip
    itself = client.patch(f"/api/profiles/{mine['id']}", json={"previous_profile_id": mine["id"]})
    assert itself.status_code == 422
    other = client.post("/api/engagements", json={"name": "Other"}).json()
    body = {"stakeholder_group": "Ramp", "interview_type": "practice"}
    theirs = client.post(f"/api/engagements/{other['id']}/profiles", json=body).json()
    crossed = client.patch(
        f"/api/profiles/{mine['id']}", json={"previous_profile_id": theirs["id"]}
    )
    assert crossed.status_code == 422
    cleared = client.patch(f"/api/profiles/{mine['id']}", json={"stakeholder_group": None})
    assert cleared.status_code == 422  # still needs a role or a group
    assert cleared.json()["error"]["details"]["field"] == "role_id"


def test_missing_engagement_or_profile(client: TestClient) -> None:
    assert client.get("/api/engagements/nope/profiles").status_code == 404
    body = {"stakeholder_group": "Ramp", "interview_type": "practice"}
    assert client.post("/api/engagements/nope/profiles", json=body).status_code == 404
    assert (
        client.patch("/api/profiles/nope", json={"interview_type": "practice"}).status_code == 404
    )
