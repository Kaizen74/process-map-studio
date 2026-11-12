"""Starting an engagement from a Capability Compass hand-off, and What we are testing (Eric's
brief, 2026-11-12; DECISIONS 95). API_CONTRACT → Capability Compass hand-off. Uses the sample
file Eric gave (fictional data) and deliberately broken copies. No AI call anywhere."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import AppConfig
from app.db import session_scope
from app.main import create_app
from app.repositories.tables import AuditRow, Claim, Element, Source
from tests.paths import BACKEND_ROOT

SAMPLE = BACKEND_ROOT / "tests" / "fixtures" / "compass" / "meridian_compass_handoff.json"


def handoff() -> dict[str, Any]:
    return dict(json.loads(SAMPLE.read_text(encoding="utf-8")))


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


def preview(client: TestClient, file: Any) -> Any:
    return client.post("/api/compass/preview", json={"handoff": file})


def message(response: Any) -> str:
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["field"] in {"handoff", "compass"}
    return str(response.json()["error"]["message"])


def start(client: TestClient, pilot: str = "VS-01", **scope: Any) -> Any:
    found = preview(client, handoff()).json()
    chosen = next(p for p in found["pilots"] if p["ref"] == pilot)
    body = {
        "name": chosen["name"], "process_name": chosen["process_name"],
        "process_kpi": chosen["process_kpi"], "industry": chosen["industry"],
        "in_scope_roles": chosen["in_scope_roles"], "role_names": chosen["in_scope_roles"],
        "compass": {"handoff": handoff(), "pilot_ref": pilot}, **scope,
    }  # fmt: skip
    return client.post("/api/engagements", json=body)


# --- Preview --------------------------------------------------------------------------------


def test_the_preview_lists_each_pilot_with_ids_exactly_as_received(client: TestClient) -> None:
    response = preview(client, handoff())
    assert response.status_code == 200, response.text
    found = response.json()
    assert (found["key"], found["ready"], found["open"]) == ("MERIDIAN", True, [])
    assert [(p["ref"], p["cluster_ref"], p["cluster_name"]) for p in found["pilots"]] == [
        ("VS-02", "CAP-03", "Technology, Data & AI"),
        ("VS-01", "CAP-04", "Commercial Leadership"),
    ]
    bid = found["pilots"][1]
    assert bid["name"] == "MERIDIAN VS-01 Bid to contract renewal"
    assert bid["process_name"] == "Bid to contract renewal"
    assert bid["process_kpi"].startswith("Win rate on renewals")
    assert bid["industry"] == "Aviation, Logistics & Transportation"
    assert bid["in_scope_roles"][0] == "Head of Pricing / Revenue Management"
    assert len(bid["interview_prompts"]) == 2 and found["pilots"][0]["interview_prompts"] == []
    assert bid["cell_refs"] == ["CAP-04.Structure", "CAP-04.People", "CAP-04.Process",
                                "CAP-04.Culture"]  # fmt: skip
    assert [p["ref"] for p in found["principles"]] == ["P1", "P2", "P3", "P4"]
    assert found["principles"][1]["refuted_by"].startswith("Three or more routes")
    assert client.get("/api/engagements").json() == []  # nothing applied


def test_a_later_1x_file_with_unknown_fields_is_read_and_not_ready_is_a_warning(
    client: TestClient,
) -> None:
    file = handoff()
    file["format_version"] = "1.4"
    file["something_new"] = {"ignored": True}
    file["readiness"] = {"ready": False, "verdict": "Two clusters unscored",
                         "open": ["Score CAP-05", "Score CAP-06"]}  # fmt: skip
    found = preview(client, file)
    assert found.status_code == 200, found.text
    assert found.json()["ready"] is False
    assert found.json()["verdict"] == "Two clusters unscored"
    assert found.json()["open"] == ["Score CAP-05", "Score CAP-06"]


def test_broken_files_are_refused_in_plain_language(client: TestClient) -> None:
    wrong = handoff()
    wrong["format"] = "compass-return"
    assert message(preview(client, wrong)) == (
        "This isn't a Capability Compass hand-off file (its format is “compass-return”, not "
        "“compass-handoff”)."
    )
    assert "isn't a Capability Compass hand-off file" in message(preview(client, ["a", "list"]))
    newer = handoff()
    newer["format_version"] = "2.0"
    assert message(preview(client, newer)) == (
        "This hand-off is version 2.0. This app reads version 1 files."
    )
    keyless = handoff()
    del keyless["engagement"]["key"]
    assert message(preview(client, keyless)).startswith("This hand-off has no engagement key")
    nowhere = handoff()
    nowhere["pilots"][1]["cluster_ref"] = "CAP-99"
    assert message(preview(client, nowhere)) == (
        "Pilot VS-01 points to cluster CAP-99, which isn't in this file. Export it again from "
        "Capability Compass."
    )
    empty = handoff()
    empty["pilots"] = []
    empty["for_apps"]["process_map_studio"]["engagements"] = []
    assert message(preview(client, empty)) == (
        "This hand-off names no pilot for Process Map Studio."
    )


# --- Creating the engagement ------------------------------------------------------------------


def test_an_engagement_starts_from_a_pilot_and_keeps_its_ids(
    client: TestClient, settings_config: AppConfig
) -> None:
    made = start(client)
    assert made.status_code == 201, made.text
    engagement = made.json()
    assert engagement["name"] == "MERIDIAN VS-01 Bid to contract renewal"
    assert engagement["process_name"] == "Bid to contract renewal"
    assert engagement["process_kpi"].startswith("Win rate on renewals")
    assert engagement["industry"] == "Aviation, Logistics & Transportation"
    link = engagement["compass"]
    assert (link["key"], link["pilot_ref"], link["cluster_ref"]) == ("MERIDIAN", "VS-01", "CAP-04")
    assert link["cluster_name"] == "Commercial Leadership"
    assert link["cell_refs"][1] == "CAP-04.People" and len(link["cell_refs"]) == 4
    assert len(link["interview_prompts"]) == 2 and link["ready"] is True
    eid = engagement["id"]
    roles = client.get(f"/api/engagements/{eid}/roles").json()
    assert [(r["name"], r["lane_order"]) for r in roles] == [
        ("Head of Pricing / Revenue Management", 1), ("Global Head, Commercial Excellence", 2),
        ("Bid & Solutions Architect", 3), ("VP Global Account Management", 4),
    ]  # fmt: skip
    testing = client.get(f"/api/engagements/{eid}/testing").json()
    assert [(t["ref"], t["origin"], t["verdict"], t["evidence_refs"]) for t in testing] == [
        (ref, "compass", "open", []) for ref in ("P1", "P2", "P3", "P4")
    ]
    assert testing[0]["text"] == "Decisions are made at the station, by one named role."
    # Prompts are prompts: no source, claim or step comes from the file.
    assert client.get(f"/api/engagements/{eid}/sources").json() == []
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert session.scalars(select(Source)).all() == []
        assert session.scalars(select(Claim)).all() == []
        assert session.scalars(select(Element)).all() == []
        [row] = session.scalars(select(AuditRow).where(AuditRow.engagement_id == eid)).all()
        assert row.action == "Created engagement"
        assert row.after["compass"] == {"key": "MERIDIAN", "pilot_ref": "VS-01",
                                        "cluster_ref": "CAP-04"}  # fmt: skip
        assert (row.after["roles"], row.after["testing"]) == (4, 4)
    # A later scope edit never changes the link.
    patched = client.patch(f"/api/engagements/{eid}", json={"process_kpi": "Win rate"})
    assert patched.json()["compass"] == link and patched.json()["process_kpi"] == "Win rate"


def test_what_eric_typed_wins_and_roles_he_unticked_are_not_created(client: TestClient) -> None:
    found = preview(client, handoff()).json()["pilots"][1]
    made = client.post("/api/engagements", json={
        "name": "Renewals", "process_kpi": "My own KPI", "industry": found["industry"],
        "role_names": ["Bid & Solutions Architect", "bid & solutions architect", "  "],
        "compass": {"handoff": handoff(), "pilot_ref": "VS-01"},
    })  # fmt: skip
    assert made.status_code == 201, made.text
    assert (made.json()["name"], made.json()["process_kpi"]) == ("Renewals", "My own KPI")
    assert made.json()["process_name"] == ""  # not sent, so not filled behind his back
    roles = client.get(f"/api/engagements/{made.json()['id']}/roles").json()
    assert [r["name"] for r in roles] == ["Bid & Solutions Architect"]


def test_a_bad_hand_off_or_pilot_creates_nothing(client: TestClient) -> None:
    wrong = handoff()
    wrong["format"] = "something-else"
    refused = client.post("/api/engagements", json={
        "name": "X", "compass": {"handoff": wrong, "pilot_ref": "VS-01"}})  # fmt: skip
    assert "isn't a Capability Compass hand-off file" in message(refused)
    missing = client.post("/api/engagements", json={
        "name": "X", "compass": {"handoff": handoff(), "pilot_ref": "VS-09"}})  # fmt: skip
    assert message(missing) == "Pilot VS-09 isn't in this hand-off."
    assert client.get("/api/engagements").json() == []


def test_without_a_hand_off_the_app_works_as_before(client: TestClient) -> None:
    made = client.post("/api/engagements", json={"name": "Load control"})
    assert made.status_code == 201 and made.json()["compass"] is None
    eid = made.json()["id"]
    assert client.get(f"/api/engagements/{eid}/testing").json() == []
    assert client.get(f"/api/engagements/{eid}/roles").json() == []
    assert client.get(f"/api/engagements/{eid}/readiness").status_code == 200


# --- What we are testing ----------------------------------------------------------------------


def test_eric_adds_a_hypothesis_and_sets_verdicts_with_the_codes_behind_them(
    client: TestClient,
) -> None:
    eid = start(client).json()["id"]
    added = client.post(f"/api/engagements/{eid}/testing", json={
        "ref": "H2", "text": "Pricing sits with regional sales, not a central desk.",
        "refuted_by": "A central desk signing off most renewals."})  # fmt: skip
    assert added.status_code == 201, added.text
    assert (added.json()["ref"], added.json()["origin"], added.json()["verdict"]) == (
        "H2", "owner", "open")  # fmt: skip
    again = client.post(f"/api/engagements/{eid}/testing", json={"ref": "h2", "text": "Same"})
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "There is already an item H2."
    minted = client.post(f"/api/engagements/{eid}/testing", json={"ref": "CAP-09", "text": "No"})
    assert minted.status_code == 422
    assert minted.json()["error"]["message"] == (
        "Give the ID as written in the other app, for example H2 or P5."
    )
    items = {t["ref"]: t for t in client.get(f"/api/engagements/{eid}/testing").json()}
    assert list(items) == ["P1", "P2", "P3", "P4", "H2"]

    p1 = items["P1"]["id"]
    bare = client.patch(f"/api/testing/{p1}", json={"verdict": "refuted"})
    assert bare.status_code == 422
    assert bare.json()["error"]["message"] == (
        "Add the step or discrepancy codes this verdict rests on."
    )
    odd = client.patch(
        f"/api/testing/{p1}", json={"verdict": "refuted", "evidence_refs": ["CAP-1"]}
    )
    assert odd.status_code == 422 and odd.json()["error"]["details"]["field"] == "evidence_refs"
    done = client.patch(
        f"/api/testing/{p1}",
        json={
            "verdict": "refuted",
            "evidence_refs": ["X2", "s-04", "X2"],
            "note": "Two roles decide.",
        },
    )
    assert done.status_code == 200, done.text
    assert (done.json()["verdict"], done.json()["evidence_refs"], done.json()["note"]) == (
        "refuted", ["X2", "S-04"], "Two roles decide.")  # fmt: skip
    assert client.patch(f"/api/testing/{p1}", json={"verdict": "maybe"}).status_code == 422
    # A principle keeps the wording it arrived with and can't be removed; Eric's own can.
    assert client.patch(f"/api/testing/{p1}", json={"text": "Changed"}).status_code == 409
    assert client.delete(f"/api/testing/{p1}").status_code == 409
    h2 = items["H2"]["id"]
    assert client.patch(f"/api/testing/{h2}", json={"text": "Pricing sits centrally."}).json()[
        "text"] == "Pricing sits centrally."  # fmt: skip
    assert client.delete(f"/api/testing/{h2}").status_code == 204
    assert client.delete(f"/api/testing/{h2}").status_code == 404
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        actions = [
            r.action for r in session.scalars(select(AuditRow).where(AuditRow.engagement_id == eid))
        ]
    assert actions == ["Created engagement", "Added testing item", "Set testing verdict",
                       "Edited testing item", "Removed testing item"]  # fmt: skip


def test_a_hidden_name_is_refused_in_a_testing_item(client: TestClient) -> None:
    eid = client.post("/api/engagements", json={"name": "Load control"}).json()["id"]
    assert client.post(f"/api/engagements/{eid}/redaction-terms",
                       json={"term": "Priya Nair", "replacement": "Load controller"}
                       ).status_code == 201  # fmt: skip
    refused = client.post(
        f"/api/engagements/{eid}/testing", json={"ref": "H1", "text": "Priya Nair decides alone."}
    )
    assert refused.status_code == 422
    assert "names to hide" in refused.json()["error"]["message"]


def test_the_sample_file_itself_is_untouched_by_reading(client: TestClient) -> None:
    file = handoff()
    before = copy.deepcopy(file)
    preview(client, file)
    assert file == before


def test_the_frontend_compass_sample_matches_the_backend(client: TestClient) -> None:
    """frontend/tests/fixtures/compass_sample.json: the preview of the sample file, the link the
    engagement keeps and its testing items, exactly as the backend sends them, so the screens'
    tests use real shapes. Not a PRD baseline. Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    engagement = start(client).json()
    testing = client.get(f"/api/engagements/{engagement['id']}/testing").json()
    bundle = {
        "preview": preview(client, handoff()).json(),
        "link": engagement["compass"],
        "testing": [{**item, "id": f"t{n}"} for n, item in enumerate(testing, start=1)],
    }
    matches_baseline("compass_sample.json", bundle, FRONTEND_FIXTURES)
