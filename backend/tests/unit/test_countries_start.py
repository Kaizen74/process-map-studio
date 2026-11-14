"""The country on an engagement, and starting a country from another country's engagement
(2026-11-13, Eric's brief "the same process in another country" §4.1-4.2; DECISIONS 98; PRD §3.19).

The Compass samples (fictional) are Arden (`MERIDIAN`), Belmar (`MERIDIANBE`) and Caldera
(`MERIDIANCA`, no pilot), each with pilot `VS-01` where it has one. Mocked: no key, no network."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import session_scope
from app.repositories.tables import (
    Element,
    MapVersion,
    RedactionTerm,
    Role,
    SharedCode,
    Source,
)
from app.services.compass import same_frame
from tests.paths import BACKEND_ROOT
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_compass_handoff import preview
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_roles_choose_remove import audit_actions

__all__ = ["drafted"]

COUNTRIES = BACKEND_ROOT / "tests" / "fixtures" / "compass" / "countries"


def packet(country: str) -> dict[str, Any]:
    return dict(json.loads((COUNTRIES / f"{country}_compass_handoff.json").read_text("utf-8")))


def start_country(client: TestClient, country: str, **more: Any) -> Any:
    """Start the country's VS-01 engagement from its packet, as the dialog does."""
    found = preview(client, packet(country))
    assert found.status_code == 200, found.text
    pilot = next(p for p in found.json()["pilots"] if p["ref"] == "VS-01")
    body = {
        "name": pilot["name"], "process_name": pilot["process_name"],
        "process_kpi": pilot["process_kpi"], "industry": pilot["industry"],
        "in_scope_roles": pilot["in_scope_roles"], "role_names": pilot["in_scope_roles"],
        "compass": {"handoff": packet(country), "pilot_ref": "VS-01"}, **more,
    }  # fmt: skip
    return client.post("/api/engagements", json=body)


def said(response: Any) -> str:
    return str(response.json()["error"]["message"])


def count(client: TestClient, table: Any, engagement_id: str) -> int:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        column = table.engagement_id
        query = select(func.count()).select_from(table).where(column == engagement_id)
        return int(session.scalar(query) or 0)


def elements_of(client: TestClient, engagement_id: str) -> int:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        query = (select(func.count()).select_from(Element).join(MapVersion)
                 .where(MapVersion.engagement_id == engagement_id))  # fmt: skip
        return int(session.scalar(query) or 0)


# --- 4.1 The country on an engagement -------------------------------------------------------


def test_the_packet_gives_the_country_and_the_same_pilot_ref(client: TestClient) -> None:
    for country, key in (("arden", "MERIDIAN"), ("belmar", "MERIDIANBE")):
        found = preview(client, packet(country)).json()
        assert (found["key"], found["country"]) == (key, country.title())
    arden = start_country(client, "arden")
    belmar = start_country(client, "belmar")
    for made, country in ((arden, "Arden"), (belmar, "Belmar")):
        assert made.status_code == 201, made.text
        body = made.json()
        assert (body["country"], body["compass"]["country"]) == (country, country)
        assert body["compass"]["pilot_ref"] == "VS-01"  # acceptance test 2
    listed = {e["id"]: e["country"] for e in client.get("/api/engagements").json()}
    assert listed == {arden.json()["id"]: "Arden", belmar.json()["id"]: "Belmar"}


def test_a_country_from_the_packet_is_locked_and_any_other_is_editable(client: TestClient) -> None:
    arden = start_country(client, "arden").json()
    locked = client.patch(f"/api/engagements/{arden['id']}", json={"country": "Belmar"})
    assert locked.status_code == 409
    assert said(locked) == (
        "The country comes from the Capability Compass hand-off, so it can't be changed here."
    )
    same = client.patch(f"/api/engagements/{arden['id']}", json={"country": "Arden"})
    assert same.status_code == 200  # sending it unchanged is fine
    plain = client.post("/api/engagements", json={"name": "Load control"}).json()
    assert plain["country"] == "" and plain["reference_engagement_id"] is None
    edited = client.patch(f"/api/engagements/{plain['id']}", json={"country": "  Caldera "})
    assert edited.status_code == 200 and edited.json()["country"] == "Caldera"
    two_lines = client.patch(f"/api/engagements/{plain['id']}", json={"country": "A\nB"})
    assert two_lines.status_code == 422
    assert said(two_lines) == "Country: one line of up to 120 characters."
    assert "Edited process scope" in [r["action"] for r in audit_actions(client, plain["id"])]


def test_frames_are_told_apart_by_key_or_cluster() -> None:
    assert same_frame("MERIDIANBE", "CAP-04", "MERIDIAN", "CAP-99")
    assert same_frame("MERIDIANBE", "CAP-04", "MERIDIANCA", "CAP-99")  # two countries of a frame
    assert not same_frame("MERIDIANBE", "CAP-04", "MERIDIANBE", "CAP-04")  # the same workspace
    assert not same_frame("ACMEBE", "CAP-01", "MERIDIAN", "CAP-02")
    assert not same_frame("MERIDIANXYZW", "CAP-01", "MERIDIAN", "CAP-02")  # four letters: no
    assert same_frame("ACME", "CAP-04", "MERIDIAN", "CAP-04")  # the brief's fallback: same cluster


def test_caldera_has_no_pilot_and_is_refused_in_plain_words(client: TestClient) -> None:
    refused = preview(client, packet("caldera"))
    assert refused.status_code == 422
    assert said(refused) == "This hand-off names no pilot for Process Map Studio."


# --- 4.2 Start a country from another country ------------------------------------------------


def test_belmar_is_offered_ardens_scope_and_copies_only_that(client: TestClient) -> None:
    """Acceptance test 1: accepting copies the scope card, conventions and lanes, nothing else."""
    assert preview(client, packet("belmar")).json()["pilots"][0]["same_process"] == []
    arden = start_country(client, "arden").json()
    aid = arden["id"]
    client.patch(f"/api/engagements/{aid}", json={
        "trigger": "Renewal due in 120 days", "end_point": "Contract signed",
        "conventions": {"granularity": "fine"}, "confidential_terms": ["Arden Air"]})  # fmt: skip
    hide = {"term": "Priya Nair", "replacement": "Bid & Solutions Architect"}
    client.post(f"/api/engagements/{aid}/redaction-terms", json=hide)
    roles = client.get(f"/api/engagements/{aid}/roles").json()
    client.patch(f"/api/roles/{roles[0]['id']}", json={"aliases": ["Priya's desk"]})
    offered = preview(client, packet("belmar")).json()["pilots"][0]["same_process"]
    assert offered == [{"engagement_id": aid, "name": arden["name"], "country": "Arden",
                        "process_name": "Bid to contract renewal",
                        "has_published": False}]  # fmt: skip
    # Arden's own packet doesn't offer Arden (the same workspace is not another country).
    assert preview(client, packet("arden")).json()["pilots"][1]["same_process"] == []
    lanes = [r["name"] for r in roles][:3]
    made = start_country(client, "belmar", role_names=lanes, reference_engagement_id=aid,
                         process_kpi=None)  # fmt: skip
    assert made.status_code == 422  # a scope field sent empty is refused as before
    made = start_country(client, "belmar", role_names=lanes, reference_engagement_id=aid)
    assert made.status_code == 201, made.text
    belmar = made.json()
    bid = belmar["id"]
    assert (belmar["reference_engagement_id"], belmar["reference_engagement_name"]) == (
        aid, arden["name"])  # fmt: skip
    assert (belmar["country"], belmar["compass"]["key"]) == ("Belmar", "MERIDIANBE")
    # What the dialog sent wins; what it left out comes from Arden; conventions always do.
    assert (belmar["trigger"], belmar["end_point"]) == ("Renewal due in 120 days",
                                                        "Contract signed")  # fmt: skip
    assert belmar["conventions"]["granularity"] == "fine"
    assert [r["name"] for r in client.get(f"/api/engagements/{bid}/roles").json()] == lanes
    # Nothing else crossed: no source, map, code, name to hide, alias or confidential term.
    for table in (Source, SharedCode, RedactionTerm):
        assert count(client, table, bid) == 0, table.__tablename__
    assert elements_of(client, bid) == 0
    assert belmar["confidential_terms"] == []
    assert all(r["aliases"] == [] for r in client.get(f"/api/engagements/{bid}/roles").json())
    row = next(r for r in audit_actions(client, bid) if r["action"] == "Created engagement")
    assert row["after"]["reference_engagement_id"] == aid
    gone = start_country(client, "belmar", reference_engagement_id="nope")
    assert gone.status_code == 404
    assert gone.json()["error"]["details"]["field"] == "reference_engagement_id"


def test_map_this_process_in_another_country_needs_a_published_map(drafted: Drafted) -> None:
    client, eid = drafted.client, drafted.engagement_id
    url = f"/api/engagements/{eid}/another-country"
    early = client.post(url, json={"country": "Belmar"})
    assert early.status_code == 409
    assert said(early) == (
        "Publish a version of this engagement first: another country starts from a published map."
    )
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    client.patch(f"/api/engagements/{eid}", json={"country": "Arden"})
    assert said(client.post(url, json={"country": " "})) == "Type the country this map will cover."
    assert said(client.post(url, json={"country": "arden"})) == (
        "This engagement already covers Arden."
    )
    assert client.post(url, json={"country": "Belmar", "role_ids": ["x"]}).status_code == 422
    lanes = client.get(f"/api/engagements/{eid}/roles").json()
    made = client.post(
        url, json={"country": "Belmar", "role_ids": [lanes[1]["id"], lanes[0]["id"]]}
    )
    assert made.status_code == 201, made.text
    new = made.json()
    first = client.get(f"/api/engagements/{eid}").json()
    assert new["name"] == f"{first['process_name'] or first['name']} — Belmar"
    assert (new["country"], new["reference_engagement_id"], new["compass"]) == ("Belmar", eid, None)
    for field in ("process_name", "trigger", "end_point", "process_kpi", "in_scope_roles",
                  "conventions"):  # fmt: skip
        assert new[field] == first[field], field
    # Lane names only, in lane order; nothing of the map, sources or names to hide.
    assert [r["name"] for r in client.get(f"/api/engagements/{new['id']}/roles").json()] == [
        lanes[0]["name"], lanes[1]["name"]]  # fmt: skip
    for table in (Source, SharedCode, RedactionTerm):
        assert count(client, table, new["id"]) == 0, table.__tablename__
    assert elements_of(client, new["id"]) == 0
    assert client.get(f"/api/engagements/{new['id']}/versions").json() == []
    assert "Started this process in another country" in [
        r["action"] for r in audit_actions(client, new["id"])]  # fmt: skip
    assert count(client, Role, eid) == len(lanes)  # the first one untouched
