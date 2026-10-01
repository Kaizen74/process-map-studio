"""Reviewing steps (API_CONTRACT.md → Review, PRD §3.5 locking, §5.7.5): confirm, reject, restore,
their rules, audit rows and the refreshed lint report. Real database, Claude mocked, on the
illustrative Appendix A engagement."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.config import AppConfig
from app.db import session_scope
from app.repositories import elements as map_repo
from app.repositories.tables import MapVersion
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, run_draft, with_key


@dataclass
class Drafted:
    client: TestClient
    engagement_id: str
    version_id: str
    ids: dict[str, str]  # label → element ID

    def act(self, label: str, action: str) -> Any:
        return self.client.post(f"/api/elements/{self.ids[label]}/{action}")

    def audit(self) -> list[dict[str, Any]]:
        response = self.client.get(f"/api/versions/{self.version_id}/audit")
        assert response.status_code == 200, response.text
        return list(response.json())


@pytest.fixture()
def drafted(settings_config: AppConfig) -> Iterator[Drafted]:
    for client in make_client(settings_config):
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        built = fixture_engagement.build(with_key(client))
        job = run_draft(client, built.engagement_id)
        graph = client.get(f"/api/versions/{job['target_id']}/graph").json()
        ids = {e["label"]: e["id"] for e in graph["elements"]}
        yield Drafted(client, built.engagement_id, job["target_id"], ids)


def test_confirming_locks_a_step_and_is_audited(drafted: Drafted) -> None:
    response = drafted.act("Draft load plan", "confirm")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_status"] == "confirmed" and body["label"] == "Draft load plan"
    assert body["evidence"]  # the full element, as GET /elements/{eid}
    # Confirming again changes nothing and writes no second row.
    assert drafted.act("Draft load plan", "confirm").json()["review_status"] == "confirmed"
    [row] = drafted.audit()
    assert (row["actor"], row["action"], row["target_label"]) == (
        "Owner",
        "Confirmed step",
        "Draft load plan",
    )
    assert (row["before"], row["after"]) == (
        {"review_status": "draft"},
        {"review_status": "confirmed"},
    )
    cards = drafted.client.get("/api/engagements").json()
    [card] = [c for c in cards if c["id"] == drafted.engagement_id]
    assert card["review_progress"] == {"reviewed": 1, "total": 10}  # v1.10 A.5


def test_rejecting_is_reversible_and_refreshes_lint(drafted: Drafted) -> None:
    lint_url = f"/api/versions/{drafted.version_id}/lint"
    assert drafted.client.get(lint_url).json()["failures"] == []
    assert drafted.act("Resolve or offload", "reject").json()["review_status"] == "rejected"
    # The rejected step leaves the map, so the decision loses its "No" exit (L4).
    failures = drafted.client.get(lint_url).json()["failures"]
    assert [f["rule"] for f in failures] == ["L4"]
    conflict = drafted.act("Resolve or offload", "confirm")
    assert conflict.status_code == 409
    assert (
        conflict.json()["error"]["message"]
        == "This step is rejected. Restore it before confirming it."
    )
    assert drafted.act("Resolve or offload", "restore").json()["review_status"] == "draft"
    assert drafted.client.get(lint_url).json()["failures"] == []
    assert [r["action"] for r in drafted.audit()] == [
        "Restored step",
        "Rejected step",
    ]  # newest first


def test_only_a_rejected_step_can_be_restored(drafted: Drafted) -> None:
    response = drafted.act("Issue load sheet", "restore")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Only a rejected step can be restored."
    assert drafted.audit() == []


def test_a_confirmed_step_can_still_be_rejected(drafted: Drafted) -> None:
    drafted.act("Issue load sheet", "confirm")
    assert drafted.act("Issue load sheet", "reject").json()["review_status"] == "rejected"


def test_start_and_end_are_not_reviewed(drafted: Drafted) -> None:
    for label in ("Flight scheduled", "Final load sheet issued"):
        response = drafted.act(label, "confirm")
        assert response.status_code == 422
        assert "change them on Setup" in response.json()["error"]["message"]


def test_a_published_version_cant_change(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        session.execute(
            update(MapVersion).where(MapVersion.id == drafted.version_id).values(state="published")
        )
    response = drafted.act("Draft load plan", "confirm")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "This version is published and can't be changed. Reopen it as a new draft."
    )


def test_missing_steps_and_versions_are_not_found(drafted: Drafted) -> None:
    for action in ("confirm", "reject", "restore"):
        response = drafted.client.post(f"/api/elements/nope/{action}")
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "That step doesn't exist."
    assert drafted.client.get("/api/versions/nope/audit").status_code == 404


def test_the_audit_log_hides_names(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        map_repo.update_element(
            session, drafted.ids["Issue load sheet"], {"label": "Priya Nair issues"}
        )
    drafted.act("Issue load sheet", "confirm")
    [row] = drafted.audit()
    assert "Priya" not in row["target_label"]
    assert row["target_label"].endswith("issues")
