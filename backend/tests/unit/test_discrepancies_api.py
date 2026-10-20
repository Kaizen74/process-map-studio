"""Discrepancies with codes, impact classes and verdicts (P13a-3b; API_CONTRACT.md → Discrepancies;
PRD §3.17.3-3.17.6, Appendix A.12): the A.12 table end to end, codes kept across a refresh and a
reopen, never reused, Eric's verdict winning, a risk flag changing the impact but not the code,
and a control the organisation intends never suggested for deletion (§3.15)."""

from __future__ import annotations

from typing import Any

import pytest

from app.db import session_scope
from app.repositories import audit, versions
from app.services import ai_service
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.uploads import wait_for_jobs


def items(r: Reality, version_id: str | None = None) -> list[dict[str, Any]]:
    url = f"/api/versions/{version_id or r.version_id}/discrepancies"
    response = r.engagement.client.get(url)
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


def by_code(r: Reality, version_id: str | None = None) -> dict[str, dict[str, Any]]:
    return {i["code"]: i for i in items(r, version_id) if i["code"]}


def test_a12_codes_impact_and_verdicts(reality: Reality, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_ai(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the discrepancy engine called Claude")

    monkeypatch.setattr(ai_service, "call_claude", no_ai)  # RT7
    found = items(reality)
    assert [(i["code"], i["types"], i["title"], i["impact_class"],
             (i["verdict"] or {}).get("suggested")) for i in found] == [
        ("X1", ["D1", "D11"], "Approve load plan", "control_exposure", "correct"),
        ("X2", ["D8", "D14"], "Load and return LIR", "time_impact", "correct"),
        ("X3", ["D13"], "Draft load plan: design gap", "time_impact", "rewrite"),
        ("X4", ["D4"], "Draft load plan", "capacity_drain", "ask"),
        ("X5", ["D2"], "Manual weight override", "workaround", "ask"),
        ("X6", ["D2"], "Resolve or offload", "workaround", "ask"),
        ("X7", ["D2", "D6"], "Busy wave? → Read report at aircraft", "workaround", "ask"),
        ("X8", ["D12"], "Deviation in limits?", "workaround", "ask"),
        ("X9", ["D2"], "Approve deviation", "workaround", "ask"),
        (None, ["D9"], "Parallel routes", None, None),
    ]  # fmt: skip
    x1, x2, x7 = found[0], found[1], found[6]
    assert x1["delta"] == {"value": 100.0, "unit": "pct", "kind": "measured",
                           "label": "never recorded; 100% of cases"}  # fmt: skip
    assert x1["impact_note"] == "potential control exposure, for the control owner to confirm"
    assert x1["evidence"] == {"documents": 1, "interviews": 0, "system_cases": 200}
    assert [d["type"] for d in x2["deltas"]] == ["D8", "D14"]
    assert x2["hours_per_month"] > 0 and x2["verdict"]["reason"] == (
        "Practice misses the target (10) while the documented way meets it.")  # fmt: skip
    assert (
        x7["verdict"]["reason"] == "The SME's stated reason suggests codify; confirm the gap class."
    )
    assert x7["location"] == {"kind": "run",
                              "keys": ["busy-wave", "read-report-at-aircraft"]}  # fmt: skip
    assert all((i["status"] == "seen" and i["verdict"] is None) or i["verdict"]["decided"] is None
               for i in found)  # fmt: skip


def test_codes_are_kept_across_a_refresh_and_a_reopen(reality: Reality) -> None:
    """A code belongs to a location: the same location keeps its code in every later version, and
    a refresh keeps what is found there (Eric's system alignment follows the refreshed steps)."""
    first = {c: i["title"] for c, i in by_code(reality).items()}
    types = {c: i["types"] for c, i in by_code(reality).items()}
    assert {c: i["title"] for c, i in by_code(reality).items()} == first  # asked again
    client = reality.engagement.client
    assert client.post(f"/api/versions/{reality.version_id}/refresh").status_code == 202
    wait_for_jobs(client)
    refreshed = by_code(reality)
    assert {c: i["title"] for c, i in refreshed.items()} == first
    assert {c: i["types"] for c, i in refreshed.items()} == types
    assert (refreshed["X3"]["status"], refreshed["X3"]["types"]) == ("seen", ["D13"])
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        fresh = versions.create(session, engagement_id=reality.engagement.eid, label="v2",
                                state="draft")  # fmt: skip
        versions.copy_content(session, reality.version_id, fresh.id)
    reopened = by_code(reality, fresh.id)
    assert {c: i["title"] for c, i in reopened.items()} == first
    assert (reopened["X3"]["status"], reopened["X3"]["types"]) == ("seen", ["D13"])
    assert max(int(c[1:]) for c in refreshed) == len(first)  # no new code for a known location


def test_a_location_not_seen_keeps_its_code_and_codes_are_never_reused(reality: Reality) -> None:
    client = reality.engagement.client
    assert "X3" in by_code(reality)
    first_target = next(i for i, a in reality.anchors.items() if a == "§1")
    client.patch(f"/api/intent/{first_target}", json={"status": "dismissed"})
    gone = by_code(reality)["X3"]
    assert (gone["status"], gone["title"], gone["types"]) == (
        "not_seen", "Draft load plan: design gap", [])  # fmt: skip
    client.patch(f"/api/intent/{first_target}", json={"status": "confirmed"})
    again = by_code(reality)
    assert again["X3"]["status"] == "seen" and "X10" not in again


def test_a_risk_flag_changes_the_impact_never_the_code(reality: Reality) -> None:
    deviation = by_code(reality)["X8"]
    element = deviation["element_ids"][0]
    response = reality.engagement.client.put(
        f"/api/elements/{element}/disposition", json={"disposition": None, "risk_flag": "safety"}
    )
    assert response.status_code == 200, response.text
    after = by_code(reality)["X8"]
    assert (after["types"], after["impact_class"]) == (["D12"], "control_exposure")


def test_erics_verdict_wins_and_is_audited(reality: Reality) -> None:
    client = reality.engagement.client
    x7 = by_code(reality)["X7"]
    url = f"/api/discrepancy-items/{x7['item_id']}/verdict"
    role = reality.engagement.roles["Load control lead"]
    decided = client.put(url, json={"verdict": "codify", "note": "Keeps the slot.",
                                    "decision_owner_role_id": role})  # fmt: skip
    assert decided.status_code == 200, decided.text
    assert decided.json() == {
        "item_id": x7["item_id"],
        "code": "X7",
        "verdict_decided": "codify",
        "verdict_note": "Keeps the slot.",
        "decision_owner_role_id": role,
    }
    verdict = by_code(reality)["X7"]["verdict"]
    assert (verdict["suggested"], verdict["decided"], verdict["note"]) == (
        "ask", "codify", "Keeps the slot.")  # fmt: skip
    owner = "decision_owner_role_id"
    for body, field in (({"verdict": "delete"}, "verdict"), ({"note": "x" * 301}, "note"),
                        ({owner: "nope"}, owner)):  # fmt: skip
        bad = client.put(url, json=body)
        assert (bad.status_code, bad.json()["error"]["details"]["field"]) == (422, field)
    assert client.put(url, json={"verdict": None}).json()["verdict_decided"] is None
    assert client.put("/api/discrepancy-items/nope/verdict", json={}).status_code == 404
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = audit.list_recent(session, engagement_id=reality.engagement.eid)
    assert [r["action"] for r in rows if r["target_type"] == "discrepancy"] == [
        "Decided discrepancy verdict", "Decided discrepancy verdict"]  # fmt: skip


def test_a_control_the_organisation_intends_is_not_suggested_for_deletion(
    reality: Reality,
) -> None:
    client = reality.engagement.client

    def approve_load_plan() -> str:
        rows = client.get(f"/api/versions/{reality.version_id}/dispositions").json()
        return str(next(d["suggested"] for d in rows if d["label"] == "Approve load plan"))

    assert approve_load_plan() == "human_approves"  # §2 is a confirmed control objective
    second = next(i for i, a in reality.anchors.items() if a == "§2")
    client.patch(f"/api/intent/{second}", json={"status": "dismissed"})
    assert approve_load_plan() == "delete"  # A.11 without intent: no record, no purpose


def test_only_the_done_view_and_known_versions(reality: Reality) -> None:
    client = reality.engagement.client
    documented = client.get(f"/api/versions/{reality.version_id}/discrepancies?view=documented")
    assert (documented.status_code, documented.json()["error"]["message"]) == (
        422, "Discrepancies are worked out on the As done view.")  # fmt: skip
    assert client.get("/api/versions/nope/discrepancies").status_code == 404
    body = client.get(f"/api/versions/{reality.version_id}/discrepancies").json()
    assert (body["rules_version"], body["view"]) == ("2", "done")
    assert {i["result"] for i in body["intents"]} == {"met", "not_met", "unknown"}
