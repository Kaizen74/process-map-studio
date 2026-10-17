"""Engagement and role endpoints (API_CONTRACT.md → Engagements and roles)."""

from __future__ import annotations

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


def test_engagement_lifecycle(client: TestClient, settings_config: AppConfig) -> None:
    created = client.post("/api/engagements", json={"name": "Load control", "industry": "Aviation"})
    assert created.status_code == 201
    engagement = created.json()
    assert engagement["confidential_terms"] == [] and engagement["industry"] == "Aviation"
    listed = client.get("/api/engagements").json()
    assert listed[0]["id"] == engagement["id"]
    assert listed[0]["latest_version"] is None
    assert listed[0]["review_progress"] == {"reviewed": 0, "total": 0}
    patched = client.patch(
        f"/api/engagements/{engagement['id']}", json={"confidential_terms": ["Acme"]}
    )
    assert patched.status_code == 200 and patched.json()["confidential_terms"] == ["Acme"]
    assert client.get(f"/api/engagements/{engagement['id']}").json()["confidential_terms"] == [
        "Acme"
    ]
    deleted = client.delete(f"/api/engagements/{engagement['id']}")
    assert deleted.status_code == 204 and deleted.content == b""
    missing = client.get(f"/api/engagements/{engagement['id']}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


def test_validation_uses_the_standard_shape(client: TestClient) -> None:
    response = client.post("/api/engagements", json={"name": "  "})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "name"
    assert client.post("/api/engagements", json={}).status_code == 422


def test_roles_endpoints(client: TestClient) -> None:
    engagement_id = client.post("/api/engagements", json={"name": "E"}).json()["id"]
    first = client.post(f"/api/engagements/{engagement_id}/roles", json={"name": "Load controller"})
    second = client.post(
        f"/api/engagements/{engagement_id}/roles", json={"name": "Ramp", "is_system": False}
    )
    assert first.status_code == second.status_code == 201
    duplicate = client.post(f"/api/engagements/{engagement_id}/roles", json={"name": "ramp"})
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "CONFLICT"
    moved = client.patch(f"/api/roles/{second.json()['id']}", json={"lane_order": 1})
    assert moved.status_code == 200 and moved.json()["lane_order"] == 1
    names = [r["name"] for r in client.get(f"/api/engagements/{engagement_id}/roles").json()]
    assert names == ["Ramp", "Load controller"]
    assert client.patch("/api/roles/nope", json={"name": "x"}).status_code == 404


def test_mapping_conventions_are_set_per_engagement(client: TestClient) -> None:
    """C7a (Appendix E tier 2, criterion 58): defaults until set, the whole object sent, each
    value one of its choices, audited like the rest of the scope."""
    created = client.post("/api/engagements", json={"name": "Load control"}).json()
    assert created["conventions"] == {"granularity": "standard", "label_style": "standard",
                                      "phase_naming": "sme"}  # fmt: skip
    url = f"/api/engagements/{created['id']}"
    chosen = {"granularity": "fine", "label_style": "sme", "phase_naming": "standard"}
    saved = client.patch(url, json={"conventions": chosen})
    assert saved.status_code == 200, saved.text
    assert saved.json()["conventions"] == chosen
    assert client.get(url).json()["conventions"] == chosen
    partial = client.patch(url, json={"conventions": {"granularity": "coarse"}}).json()
    assert partial["conventions"] == {
        "granularity": "coarse",
        "label_style": "standard",
        "phase_naming": "sme",
    }  # unsent fields: the defaults
    for body, field in (
        ({"granularity": "tiny"}, "conventions.granularity"),
        ({"label_style": "fancy"}, "conventions.label_style"),
        ({"phase_naming": "x"}, "conventions.phase_naming"),
        ({"colour": "blue"}, "conventions.colour"),
    ):
        refused = client.patch(url, json={"conventions": body})
        assert refused.status_code == 422, refused.text
        assert refused.json()["error"]["details"]["field"] == field
    assert client.get(url).json()["conventions"]["granularity"] == "coarse"  # nothing saved
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = list(session.scalars(
            select(AuditRow).where(AuditRow.engagement_id == created["id"],
                                   AuditRow.action == "Edited process scope")
            .order_by(AuditRow.created_at)
        ))  # fmt: skip
        assert [r.after for r in rows] == [{"conventions": chosen},
                                           {"conventions": partial["conventions"]}]  # fmt: skip


def test_the_scope_card_says_whether_the_process_starts_or_ends_outside(client: TestClient) -> None:
    """E1 (Eric's decision 2026-10-15): two yes/no answers, no until ticked, audited like the
    rest of the scope; the Typical case draws its "Outside the organisation" lane from them."""
    created = client.post("/api/engagements", json={"name": "Load control"}).json()
    assert (created["trigger_external"], created["end_point_external"]) == (False, False)
    url = f"/api/engagements/{created['id']}"
    saved = client.patch(url, json={"trigger_external": True})
    assert saved.status_code == 200, saved.text
    assert (saved.json()["trigger_external"], saved.json()["end_point_external"]) == (True, False)
    assert client.get(url).json()["trigger_external"] is True
    refused = client.patch(url, json={"end_point_external": "perhaps"})
    assert refused.status_code == 422, refused.text
    refused = client.patch(url, json={"end_point_external": None})
    assert refused.status_code == 422, refused.text
    assert refused.json()["error"]["details"]["field"] == "end_point_external"
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = list(session.scalars(
            select(AuditRow).where(AuditRow.engagement_id == created["id"],
                                   AuditRow.action == "Edited process scope")
        ))  # fmt: skip
        assert [r.after for r in rows] == [{"trigger_external": True}]
