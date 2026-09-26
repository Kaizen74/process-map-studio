"""Engagement and role endpoints (API_CONTRACT.md → Engagements and roles)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


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
