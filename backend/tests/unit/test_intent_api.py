"""Intent statements (P13a-1; API_CONTRACT.md → Intent; PRD §3.16, constraint 25, G16): owner-stated
targets Eric types in, and statements quoted from a policy or charter that he confirms, edits,
dismisses or keeps on record. On the illustrative Appendix A engagement with the A.12 charter.
Real database, Claude mocked."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import intent as actions
from app.config import AppConfig
from app.db import session_scope
from app.repositories import audit
from app.repositories import intent as repo
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, run_draft, with_key
from tests.uploads import FIXTURES, wait_for_jobs

REALITY = FIXTURES.parent / "reality"

CHARTER = "charter_load_control.docx"
OWNER_TEXT = "Weight deviations outside tolerance are decided by the Load control lead."


@dataclass
class Engagement:
    client: TestClient
    eid: str
    roles: dict[str, str]
    charter_id: str
    graph: dict[str, Any]

    def owner_body(self, **changes: Any) -> dict[str, Any]:
        """A.12: the owner-stated policy rule on "Deviation in limits?"."""
        body = {"scope": "step", "element_stable_key": "deviation-in-limits", "phase_name": None,
                "kind": "policy_rule", "text": OWNER_TEXT, "metric": None, "comparator": None,
                "target_value": None, "unit": None,
                "owner_role_id": self.roles["Load control lead"],
                "stated_on": "2026-10-01"}  # fmt: skip
        return body | changes

    def add(self, **changes: Any) -> Any:
        return self.client.post(
            f"/api/engagements/{self.eid}/intent", json=self.owner_body(**changes)
        )

    def clause(self, anchor: str) -> dict[str, Any]:
        page = self.client.get(f"/api/sources/{self.charter_id}/segments").json()
        return dict(next(s for s in page["segments"] if s["anchor"] == anchor))

    def quoted(self, anchor: str, **fields: Any) -> str:
        """A statement quoted from the charter, as S1 intent will propose it (P13a-2)."""
        segment = self.clause(anchor)
        text = segment["text"].removeprefix(f"{anchor} ")
        row = {"engagement_id": self.eid, "scope": "process", "kind": "target",
               "origin": "document", "text": text, "source_id": self.charter_id,
               "segment_ids": [segment["id"]], "quote": text, "verification_status": "verified",
               "status": "proposed"} | fields  # fmt: skip
        with session_scope(self.client.app.state.sessions) as session:  # type: ignore[attr-defined]
            return repo.add(session, row).id


@pytest.fixture()
def engagement(settings_config: AppConfig) -> Iterator[Engagement]:
    for client in make_client(settings_config):
        built = fixture_engagement.build(with_key(client))
        data = (REALITY / CHARTER).read_bytes()
        uploaded = client.post(
            f"/api/engagements/{built.engagement_id}/sources",
            files={"file": (CHARTER, data, "application/octet-stream")},
        )
        assert uploaded.status_code == 201, uploaded.text
        wait_for_jobs(client)
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "done", job
        graph = client.get(f"/api/versions/{job['target_id']}/graph").json()
        yield Engagement(client, built.engagement_id, built.roles, uploaded.json()["id"], graph)


def audit_actions(engagement: Engagement) -> list[str]:
    """Oldest first."""
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = audit.list_recent(session, engagement_id=engagement.eid)
    return [r["action"] for r in reversed(rows) if r["target_type"] == "intent"]


def test_the_charter_is_a_policy_source_and_is_never_drafted_from(engagement: Engagement) -> None:
    source = engagement.client.get(f"/api/sources/{engagement.charter_id}").json()
    assert (source["kind"], source["text_status"]) == ("policy_or_charter", "ready")
    assert [engagement.clause(a)["anchor"] for a in ("§1", "§2", "§3", "§4")]
    cited = {c["source_id"] for e in engagement.graph["elements"] for c in e["evidence"]}
    assert engagement.charter_id not in cited
    assert engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json() == []


def test_an_owner_stated_target_is_added_confirmed_and_labelled(engagement: Engagement) -> None:
    response = engagement.add()
    assert response.status_code == 201, response.text
    view = response.json()
    assert {k: view[k] for k in ("scope", "element_stable_key", "element_label", "kind", "origin",
                                 "text", "status", "verification_status", "owner_role_name",
                                 "stated_on", "label", "quote", "source_id", "anchor")} == {
        "scope": "step", "element_stable_key": "deviation-in-limits",
        "element_label": "Deviation in limits?", "kind": "policy_rule", "origin": "owner_stated",
        "text": OWNER_TEXT, "status": "confirmed", "verification_status": "verified",
        "owner_role_name": "Load control lead", "stated_on": "2026-10-01",
        "label": "Target set by Load control lead, 1 Oct 2026", "quote": "", "source_id": None,
        "anchor": "",
    }  # fmt: skip
    listed = engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json()
    assert listed == [view]
    assert audit_actions(engagement) == ["Added intent statement"]
    # A process target with a metric; and a phase scope.
    timed = engagement.add(scope="process", element_stable_key=None, kind="target",
                           text="The load sheet is issued 10 minutes before departure.",
                           metric="cycle_time_min", comparator="at_most", target_value=10,
                           unit="min")  # fmt: skip
    assert timed.status_code == 201, timed.text
    assert (timed.json()["target_value"], timed.json()["element_stable_key"]) == (10, None)
    phased = engagement.add(scope="phase", element_stable_key=None, phase_name="Plan")
    assert (phased.status_code, phased.json()["phase_name"]) == (201, "Plan")


# Each POST rule (API_CONTRACT.md → Intent): what is sent, the field named, the message.
RULES: list[tuple[dict[str, Any], str, str]] = [
    ({"kind": "wish"}, "kind", actions.BAD_KIND),
    ({"scope": "lane"}, "scope", actions.BAD_SCOPE),
    ({"element_stable_key": "not-a-step"}, "element_stable_key", actions.BAD_STEP),
    ({"element_stable_key": "start"}, "element_stable_key", actions.BAD_STEP),
    ({"scope": "phase", "phase_name": "Boarding"}, "phase_name", actions.BAD_PHASE),
    ({"text": ""}, "text", actions.BAD_TEXT),
    ({"text": "x" * 201}, "text", actions.BAD_TEXT),
    ({"text": "One line\nand another"}, "text", actions.BAD_TEXT),
    ({"text": "Deviations are decided by Priya Nair."}, "text", actions.NAMED),
    ({"metric": "speed"}, "metric", actions.BAD_METRIC),
    ({"metric": "cycle_time_min"}, "target_value", actions.NEED_TARGET),
    ({"metric": "cycle_time_min", "comparator": "at_most", "target_value": 10, "unit": "pct"},
     "target_value", actions.NEED_TARGET),
    ({"metric": "cycle_time_min", "comparator": "at_most", "target_value": -1, "unit": "min"},
     "target_value", actions.NEED_TARGET),
    ({"target_value": 10}, "metric", actions.TARGET_WITHOUT_METRIC),
    ({"owner_role_id": None}, "owner_role_id", actions.BAD_OWNER),
    ({"owner_role_id": "not-a-role"}, "owner_role_id", actions.BAD_OWNER),
    ({"stated_on": "1 Oct 2026"}, "stated_on", actions.BAD_DATE),
    ({"stated_on": (date.today() + timedelta(days=1)).isoformat()}, "stated_on",
     actions.BAD_DATE),
]  # fmt: skip


def test_owner_stated_rules(engagement: Engagement) -> None:
    # One drafted engagement for every rule: drafting is the slow part.
    for changes, field, message in RULES:
        response = engagement.add(**changes)
        assert response.status_code == 422, (changes, response.text)
        error = response.json()["error"]
        assert (error["message"], error["details"]["field"]) == (message, field), changes
    assert engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json() == []


def test_unknown_fields_and_engagements_are_refused(engagement: Engagement) -> None:
    body = engagement.owner_body(origin="document")
    assert engagement.client.post(f"/api/engagements/{engagement.eid}/intent",
                                  json=body).status_code == 422  # fmt: skip
    missing = engagement.client.post("/api/engagements/nope/intent", json=engagement.owner_body())
    assert missing.status_code == 404
    assert engagement.client.get("/api/engagements/nope/intent").status_code == 404
    patched = engagement.client.patch("/api/intent/nope", json={"status": "confirmed"})
    assert (patched.status_code, patched.json()["error"]["message"]) == (
        404,
        actions.INTENT_MISSING,
    )
    assert engagement.client.delete("/api/intent/nope").status_code == 404


def test_a_quoted_statement_is_confirmed_edited_and_dismissed(engagement: Engagement) -> None:
    iid = engagement.quoted("§3", metric="wait_min", comparator="at_most",
                            target_value=10, unit="min")  # fmt: skip
    url = f"/api/intent/{iid}"
    view = engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json()[0]
    assert view["label"] == f"Quoted from {CHARTER} §3"
    assert (view["source_name"], view["anchor"], view["status"]) == (CHARTER, "§3", "proposed")
    confirmed = engagement.client.patch(url, json={"status": "confirmed", "note": "Checked."})
    assert confirmed.status_code == 200, confirmed.text
    assert (confirmed.json()["status"], confirmed.json()["note"]) == ("confirmed", "Checked.")
    # G5: a target value must be in the quoted text; 10 is, 15 isn't.
    wrong = engagement.client.patch(url, json={"edits": {"target_value": 15}})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["message"] == actions.NOT_IN_QUOTE
    owner = engagement.client.patch(url, json={"edits": {"stated_on": "2026-10-01"}})
    assert (owner.status_code, owner.json()["error"]["message"]) == (422, actions.OWNER_ON_DOCUMENT)
    step = {"scope": "step", "element_stable_key": "load-and-return-lir"}
    edited = engagement.client.patch(url, json={"edits": step})
    assert edited.status_code == 200, edited.text
    assert (edited.json()["scope"], edited.json()["element_label"]) == (
        "step",
        "Load and return LIR",
    )
    long_note = engagement.client.patch(url, json={"note": "x" * 301})
    assert (long_note.status_code, long_note.json()["error"]["message"]) == (422, actions.BAD_NOTE)
    bad = engagement.client.patch(url, json={"status": "maybe"})
    assert (bad.status_code, bad.json()["error"]["message"]) == (422, actions.BAD_STATUS)
    dismissed = engagement.client.patch(url, json={"status": "dismissed"})
    assert dismissed.json()["status"] == "dismissed"
    # Kept on record: a document statement is dismissed, never deleted.
    deleted = engagement.client.delete(url)
    assert deleted.status_code == 409
    assert deleted.json()["error"]["message"] == actions.DOCUMENT_DELETE
    assert audit_actions(engagement) == ["Confirmed intent statement", "Edited intent statement",
                                         "Dismissed intent statement"]  # fmt: skip
    # Nothing changed: no audit row.
    assert engagement.client.patch(url, json={"status": "dismissed"}).status_code == 200
    assert len(audit_actions(engagement)) == 3


def test_a_statement_the_checks_turned_down_cannot_be_confirmed(engagement: Engagement) -> None:
    iid = engagement.quoted("§1", verification_status="rejected", rejection_guardrail="G5")
    response = engagement.client.patch(f"/api/intent/{iid}", json={"status": "confirmed"})
    assert (response.status_code, response.json()["error"]["message"]) == (409, actions.REJECTED)
    view = engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json()[0]
    assert (view["status"], view["rejection_guardrail"]) == ("proposed", "G5")
    # It can still be dismissed.
    dismissed = engagement.client.patch(f"/api/intent/{iid}", json={"status": "dismissed"})
    assert dismissed.json()["status"] == "dismissed"


def test_an_owner_stated_statement_is_edited_and_deleted(engagement: Engagement) -> None:
    iid = engagement.add().json()["id"]
    url = f"/api/intent/{iid}"
    edited = engagement.client.patch(url, json={"edits": {"stated_on": "2026-09-15"}})
    assert edited.json()["label"] == "Target set by Load control lead, 15 Sep 2026"
    named = engagement.client.patch(url, json={"edits": {"text": "Priya Nair decides."}})
    assert (named.status_code, named.json()["error"]["message"]) == (422, actions.NAMED)
    assert engagement.client.delete(url).status_code == 204
    assert engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json() == []
    assert audit_actions(engagement) == ["Added intent statement", "Edited intent statement",
                                         "Deleted intent statement"]  # fmt: skip


def test_names_are_hidden_in_every_answer(engagement: Engagement) -> None:
    iid = engagement.quoted("§2")
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        repo.update(session, iid, {"text": "Priya Nair approves every plan.",
                                   "quote": "Priya Nair approves every plan."})  # fmt: skip
    view = engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json()[0]
    assert "Priya" not in str(view)
    assert "Nair" not in view["text"] and "Nair" not in view["quote"]


def test_the_reality_views_module_starts_off(engagement: Engagement) -> None:
    assert engagement.client.get("/api/settings").json()["reality_views_enabled"] is False
