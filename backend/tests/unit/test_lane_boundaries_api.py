"""Lane boundaries (API_CONTRACT.md → GET /versions/{vid}/lane-boundaries; PRD F.4 L5, F.6 F1
and F4, criterion 76; C8): on the sample map the load controller's claims share the ramp's
loading step; the map keeps the ramp as the one Responsible and lists the load controller as
Consulted, with a note. Read-only, names hidden. Claude mocked."""

from __future__ import annotations

from app.db import session_scope
from app.repositories import elements as map_repo
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def boundaries_url(d: Drafted) -> str:
    return f"/api/versions/{d.version_id}/lane-boundaries"


def test_shared_delivery_is_recorded_as_one_responsible_plus_consulted(drafted: Drafted) -> None:
    found = drafted.client.get(boundaries_url(drafted))
    assert found.status_code == 200
    assert [(f["label"], f["kind"], f["responsible"], f["consulted"]) for f in found.json()] == [
        ("Load and return LIR", "shared_delivery", "Ramp", ["Load controller"])]  # fmt: skip
    f = found.json()[0]
    assert f["note"] == ("Shared delivery: Load controller also take part. One Responsible "
                         "(Ramp), the others Consulted; confirm with the teams.")  # fmt: skip
    # The map's lane is the Responsible (constraint 5).
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    lanes = {r["id"]: r["name"] for r in graph["roles"]}
    step = next(e for e in graph["elements"] if e["id"] == f["element_id"])
    assert lanes[step["lane_role_id"]] == "Ramp"


def test_findings_never_change_the_map(drafted: Drafted) -> None:
    def snapshot() -> list[tuple[str, str | None, str]]:
        with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
            return [(e.id, e.lane_role_id, e.label)
                    for e in map_repo.elements(session, drafted.version_id)]  # fmt: skip

    before = snapshot()
    drafted.client.get(boundaries_url(drafted))
    assert snapshot() == before


def test_names_on_the_redaction_list_stay_hidden(drafted: Drafted) -> None:
    body = drafted.client.get(boundaries_url(drafted)).text
    terms = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/redaction-terms").json()
    names = [t["term"] for t in terms]
    assert names and not any(n in body for n in names)


def test_an_unknown_version_is_404(drafted: Drafted) -> None:
    missing = drafted.client.get("/api/versions/nope/lane-boundaries")
    assert missing.status_code == 404
    assert "That version doesn't exist." in missing.text
