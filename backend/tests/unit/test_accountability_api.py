"""The decider on paper, the system of record and how data moves (PRD §3.20; DECISIONS 110):
Eric's record on a draft, checked, audited, kept by the map file and never an edit of the step."""

from __future__ import annotations

from typing import Any

from app.services import accountability
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def graph(d: Drafted) -> dict[str, Any]:
    return dict(d.client.get(f"/api/versions/{d.version_id}/graph").json())


def deciding(d: Drafted) -> dict[str, Any]:
    return next(e for e in graph(d)["elements"] if e["kind"] in ("decision", "approval"))


def other_role(d: Drafted, not_this: str | None) -> str:
    roles = d.client.get(f"/api/engagements/{d.engagement_id}/roles").json()
    return str(next(r["id"] for r in roles if r["id"] != not_this and not r["is_system"]))


def test_the_decider_on_paper_with_its_passage_and_the_hint(drafted: Drafted) -> None:
    d = drafted
    step = deciding(d)
    url = f"/api/elements/{step['id']}/paper-decider"
    decider = step["decision"]["decider_role_id"] or step["lane_role_id"]
    paper = other_role(d, decider)
    cited = next(
        ev["segment_id"]
        for ev in step["evidence"]
        if ev["segment_id"] and ev["verified"] and ev["source_kind"] != "interview_transcript"
    )
    response = d.client.put(url, json={"status": "named", "role_id": paper, "segment_id": cited})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["paper_decider"] == {"status": "named", "role_id": paper, "segment_id": cited}
    assert body["paper_decider_role_name"] and body["paper_decider_anchor"]
    # A different role from the one deciding, and no Different role discrepancy: only a hint.
    assert body["paper_decider_hint"] == accountability.PAPER_HINT
    assert body["review_status"] == step["review_status"]  # not an edit of the step
    [row] = [r for r in d.audit() if r["action"] == "Recorded decider on paper"]
    assert row["after"]["paper_decider_role_id"] == paper
    # Kept in the map file, and the same role in practice gives no hint.
    assert next(e for e in graph(d)["elements"] if e["id"] == step["id"])["paper_decider"]
    same = d.client.put(url, json={"status": "named", "role_id": decider}).json()
    assert same["paper_decider_hint"] == "" and same["paper_decider_anchor"] == ""  # not cited
    assert d.client.put(url, json={"status": "not_named"}).json()["paper_decider"] == {
        "status": "not_named", "role_id": None, "segment_id": None,
    }  # fmt: skip
    assert d.client.put(url, json={"status": None}).json()["paper_decider"] is None


def test_the_decider_on_paper_is_checked(drafted: Drafted) -> None:
    d = drafted
    step = deciding(d)
    url = f"/api/elements/{step['id']}/paper-decider"

    def said(body: dict[str, Any]) -> tuple[int, str]:
        r = d.client.put(url, json=body)
        return r.status_code, r.json()["error"]["details"].get("field", "")

    assert said({"status": "named", "role_id": "nobody"}) == (422, "role_id")
    role = other_role(d, None)
    uncited = {"status": "named", "role_id": role, "segment_id": "not-cited"}
    assert said(uncited) == (422, "segment_id")
    assert said({"status": "maybe"}) == (422, "status")
    activity = next(e for e in graph(d)["elements"] if e["kind"] == "activity")
    refused = d.client.put(f"/api/elements/{activity['id']}/paper-decider",
                           json={"status": "not_named"})  # fmt: skip
    assert refused.status_code == 422
    confirm_all(d)
    assert publish(d).status_code == 200
    assert d.client.put(url, json={"status": "not_named"}).status_code == 409


def test_the_system_of_record_and_how_data_moves(drafted: Drafted) -> None:
    d = drafted
    step = next(e for e in graph(d)["elements"] if e["kind"] == "activity")
    url = f"/api/elements/{step['id']}/system-of-record"
    made = d.client.post(f"/api/engagements/{d.engagement_id}/roles",
                         json={"name": "Load control system", "is_system": True})  # fmt: skip
    assert made.status_code == 201, made.text
    system = made.json()["id"]
    body = d.client.put(url, json={"status": "system", "role_id": system}).json()
    assert body["system_of_record"] == {"status": "system", "role_id": system, "other": ""}
    assert body["system_role_name"] == "Load control system"
    person = {"status": "system", "role_id": other_role(d, None)}
    assert d.client.put(url, json=person).status_code == 422  # a person's role is not a system
    other = d.client.put(url, json={"status": "other", "other": "  Weighbridge   log "}).json()
    assert other["system_of_record"] == {"status": "other", "role_id": None,
                                         "other": "Weighbridge log"}  # fmt: skip
    assert d.client.put(url, json={"status": "other", "other": ""}).status_code == 422
    assert d.client.put(url, json={"status": "none"}).json()["system_of_record"]["status"] == "none"

    g = graph(d)
    lanes = {e["id"]: (e["lane_role_id"], e["kind"]) for e in g["elements"]}
    steps = {"activity", "decision", "approval"}

    def handoff(x: dict[str, Any]) -> bool:
        (a, ka), (b, kb) = lanes[x["from"]], lanes[x["to"]]
        return ka in steps and kb in steps and a != b

    line = next(x for x in g["edges"] if handoff(x))
    same_lane = next((x for x in g["edges"] if not handoff(x)), None)
    move = f"/api/versions/{d.version_id}/edges/{line['id']}/data-move"
    set_it = d.client.put(move, json={"data_move": "re_keyed"})
    assert set_it.status_code == 200, set_it.text
    assert set_it.json()["data_move"] == "re_keyed"
    assert next(x for x in graph(d)["edges"] if x["id"] == line["id"])["data_move"] == "re_keyed"
    assert d.client.put(move, json={"data_move": "telepathy"}).status_code == 422
    assert d.client.put(move, json={"data_move": None}).json()["data_move"] is None
    if same_lane is not None:
        refused = d.client.put(f"/api/versions/{d.version_id}/edges/{same_lane['id']}/data-move",
                               json={"data_move": "paper"})  # fmt: skip
        assert refused.status_code == 422
    assert {"Recorded system of record", "Recorded how data moves"} <= {
        r["action"] for r in d.audit()
    }
