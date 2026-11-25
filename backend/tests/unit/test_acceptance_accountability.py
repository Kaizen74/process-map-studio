"""Mock regression for decision rights, SOP owners, the process owner and the data lens
(2026-11-25, Eric's brief §6; DECISIONS 110): the brief's acceptance tests 1-13 on the Belmar
fixture (`tests/accountability_fixture.py`), through the real routes, Claude mocked throughout
(no call is made: nothing here asks for one). Test 14 is the rest of the suite and the checks.

The figures expected are the brief's own and those of the Compass's sample return file
`belmar_return_process_map_studio.json` (X1, X3, SOP-01 and VS-01).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.repositories.tables import Element
from app.services import accountability
from app.services import compass_return as rules
from tests.accountability_fixture import (
    CL,
    CLC,
    CM,
    PERSON,
    RFC,
    SM,
    SS,
    Built,
    Fixture,
    build,
)
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_compass_handoff import preview
from tests.unit.test_countries_start import COUNTRIES, packet

SAMPLE = {
    f["ref"]: f
    for f in json.loads((COUNTRIES / "belmar_return_process_map_studio.json").read_text("utf-8"))[
        "findings"
    ]
}
RIGHTS = ("on_paper", "decided_by", "accountable", "accountable_contested")
PERSON_REFUSED = "Name the role, not the person."


@pytest.fixture()
def fx(client: TestClient) -> Iterator[Fixture]:
    yield build(client)


def returned(b: Built, fmt: str = "json") -> Any:
    response = b.client.get(f"/api/versions/{b.version_id}/compass-return?fmt={fmt}")
    assert response.status_code == 200, response.text
    return response.json() if fmt == "json" else response.text


def by_ref(b: Built) -> dict[str, dict[str, Any]]:
    return {f["ref"]: f for f in returned(b)["findings"]}


def rights_of(f: dict[str, Any]) -> dict[str, Any]:
    return {k: f[k] for k in RIGHTS if k in f}


def set_register(b: Built) -> None:
    """Eric's SOP register on the Sources screen: the SOP's owner, updater, dates and copy."""
    sop, manual = b.sources["sop"], b.sources["manual"]
    sent = b.client.patch(f"/api/sources/{sop}", json={
        "title": "Load planning and sign-off", "owner_role_id": b.roles[SM],
        "updated_by_role_id": b.roles[SS], "version_date": "2019-04", "last_reviewed": "2019-04",
        "controlled_copy": False,
    })  # fmt: skip
    assert sent.status_code == 200, sent.text
    assert b.client.patch(f"/api/sources/{manual}",
                          json={"title": "Overtime approval"}).status_code == 200  # fmt: skip


def compare_and_class(fx: Fixture) -> dict[str, Any]:
    """Belmar compared with Arden; Eric confirms the obvious pairs, marks S-11 Belmar's own, and
    classes or keeps the differences on S-04, S-07 and S-11."""
    c = fx.client
    made = c.post(
        "/api/comparisons",
        json={
            "reference_engagement_id": fx.arden.engagement_id,
            "other_engagement_id": fx.belmar.engagement_id,
        },
    )
    assert made.status_code in (200, 201), made.text
    view = made.json()
    for p in view["pairs"]:
        if p["status"] == "proposed":
            body = {"reference_key": p["reference_key"], "other_key": p["other_key"],
                    "decision": "confirmed"}  # fmt: skip
            view = c.put(f"/api/comparisons/{view['id']}/pairs", json=body).json()
    lone = {"reference_key": None, "other_key": "file-the-contract", "decision": "only_other"}
    view = c.put(f"/api/comparisons/{view['id']}/pairs", json=lone).json()
    for d in view["differences"]:
        classed = {
            "action": "class",
            "reason_class": "chosen",
            "reason_note": "Its own delegation.",
        }
        action = classed if d["topic"] == "decision_right" else {"action": "keep"}
        r = c.put(f"/api/comparisons/{view['id']}/differences/{d['key']}", json=action)
        assert r.status_code == 200, r.text
    return dict(c.get(f"/api/comparisons/{view['id']}").json())


# --- 1-5: decision rights ---------------------------------------------------------------------


def test_1_and_2_the_four_fields_on_steps_and_on_the_d12_discrepancy(fx: Fixture) -> None:
    found = by_ref(fx.belmar)
    assert rights_of(found["S-03"]) == {"on_paper": CLC, "decided_by": SS, "accountable": CLC}
    assert rights_of(found["S-05"]) == {
        "on_paper": "Regional roster owner", "decided_by": SM,
        "accountable": "Regional roster owner", "accountable_contested": True,
    }  # fmt: skip
    assert rights_of(found["S-07"]) == {"decided_by": CM, "accountable": f"{CM} / {RFC}",
                                        "accountable_contested": True}  # fmt: skip
    assert rights_of(found["S-08"]) == {"decided_by": CL}
    assert rights_of(found["S-02"]) == {}
    # On the D12 discrepancies at S-03 and S-05: the same fields as the Compass's X1 and X3.
    for ours, theirs in (("X1", "X1"), ("X3", "X3")):
        assert found[ours]["topic"] == SAMPLE[theirs]["topic"] == "decision_right"
        assert rights_of(found[ours]) == rights_of(SAMPLE[theirs])
        assert list(rights_of(found[ours])) == list(rights_of(SAMPLE[theirs]))


def test_3_a_role_name_to_hide_is_hidden_in_all_three_fields(fx: Fixture) -> None:
    b = fx.belmar
    term = {"term": CLC, "replacement": "the load control role"}
    assert b.client.post(f"/api/engagements/{b.engagement_id}/redaction-terms",
                         json=term).status_code == 201  # fmt: skip
    found = by_ref(b)
    assert rights_of(found["S-03"]) == {
        "on_paper": "the load control role", "decided_by": SS,
        "accountable": "the load control role",
    }  # fmt: skip
    text = json.dumps(returned(b)) + returned(b, "md")
    assert CLC not in text and PERSON["belmar"] not in text
    # The last check still refuses a file that would hold it.
    assert rules.leaks(json.dumps({"on_paper": CLC}), [CLC], rules.SECRET_MARKERS)


def test_4_the_raci_view_marks_and_counts(fx: Fixture) -> None:
    b = fx.belmar
    graph = b.get(f"/api/versions/{b.version_id}/graph")
    names = {r["id"]: r["name"] for r in graph["roles"]}
    by_id = {e["id"]: e for e in graph["elements"]}
    marked = []
    for code, eid in sorted(b.steps.items()):
        r = accountability.rights(_element(by_id[eid]), names)
        if r is not None and r.split:
            marked.append(code)
    assert marked == ["S-03", "S-05", "S-07"]
    counts = accountability.raci_counts([_element(e) for e in graph["elements"]], names)
    assert (counts.decisions, counts.paper_differs, counts.split, counts.contested) == (4, 2, 3, 2)


def _element(e: dict[str, Any]) -> Any:
    from app.domain.graph import GraphElement

    return GraphElement.model_validate(e)


def test_5_a_different_decider_on_paper_shows_the_hint_and_creates_nothing(fx: Fixture) -> None:
    b, c = fx.belmar, fx.client
    draft = c.post(f"/api/versions/{b.version_id}/reopen").json()
    before = c.get(f"/api/versions/{draft['id']}/graph").json()
    reality = f"/api/versions/{draft['id']}/reality"
    codes_before = [x["code"] for x in c.get(reality).json()["codes"]]
    step = next(e for e in before["elements"] if e["code"] == "S-07")
    cited = next(ev["segment_id"] for ev in step["evidence"]
                 if ev["segment_id"] and ev["source_kind"] != "interview_transcript")  # fmt: skip
    body = {"status": "named", "role_id": b.roles[RFC], "segment_id": cited}
    done = c.put(f"/api/elements/{step['id']}/paper-decider", json=body)
    assert done.status_code == 200, done.text
    assert done.json()["paper_decider_hint"] == accountability.PAPER_HINT
    after = c.get(f"/api/versions/{draft['id']}/graph").json()
    assert len(after["elements"]) == len(before["elements"])
    assert len(after["edges"]) == len(before["edges"])
    assert [x["code"] for x in c.get(reality).json()["codes"]] == codes_before  # none made
    assert (
        next(e for e in after["elements"] if e["id"] == step["id"])["review_status"]
        == (step["review_status"])
    )  # never an edit of the step


# --- 6-8: SOP owners ------------------------------------------------------------------------


def test_6_one_sop_finding_per_sop_and_manual_matching_the_sample(fx: Fixture) -> None:
    b = fx.belmar
    set_register(b)
    found = returned(b)["findings"]
    sops = [f for f in found if f["kind"] == "sop"]
    assert [f["ref"] for f in sops] == ["SOP-01", "SOP-02"]  # none for the transcript
    ours, theirs = sops[0], SAMPLE["SOP-01"]
    fields = [
        "title",
        "owner_role",
        "updated_by",
        "version_date",
        "last_reviewed",
        "controlled_copy",
        "steps_governed",
        "steps_departing",
        "figure",
        "topic",
    ]
    assert {k: ours[k] for k in fields} == {k: theirs[k] for k in fields}
    assert [k for k in ours if k in theirs] == [k for k in theirs if k in ours]  # same order
    assert "owner_role" not in sops[1]


def test_7_a_persons_name_as_sop_owner_is_refused(fx: Fixture) -> None:
    b = fx.belmar
    for field in ("owner", "updated_by_other", "title"):
        refused = b.client.patch(f"/api/sources/{b.sources['sop']}",
                                 json={field: PERSON["belmar"]})  # fmt: skip
        assert refused.status_code == 422
        assert refused.json()["error"]["message"] == PERSON_REFUSED
    assert rules.leaks(json.dumps({"owner_role": PERSON["belmar"]}), [PERSON["belmar"]],
                       rules.SECRET_MARKERS)  # fmt: skip


def test_8_the_sources_line(fx: Fixture) -> None:
    b = fx.belmar
    set_register(b)
    counts = b.get(f"/api/engagements/{b.engagement_id}/sop-register")["counts"]
    line = (
        f"{counts['sops']} SOPs · {counts['without_owner']} without an owner · "
        f"{counts['without_updater']} with nobody to update them · "
        f"{counts['overdue']} review overdue · {counts['uncontrolled']} uncontrolled"
    )
    assert line == ("2 SOPs · 1 without an owner · 1 with nobody to update them · "
                    "0 review overdue · 1 uncontrolled")  # fmt: skip


# --- 9-13: the process at a glance, the data lens and the deviation share ---------------------


def test_9_and_12_and_13_the_process_summary_matches_the_sample(fx: Fixture) -> None:
    b = fx.belmar
    assert (
        b.client.patch(
            f"/api/engagements/{b.engagement_id}", json={"process_owner_role_id": b.roles[CM]}
        ).status_code
        == 200
    )
    view = compare_and_class(fx)
    assert view["deviation"] == {"differing": 3, "steps": 11}  # "3 of 11 steps (27%)"
    [ours] = [f for f in returned(b)["findings"] if f["kind"] == "process_summary"]
    theirs = SAMPLE["VS-01"]
    assert (ours["ref"], ours["process_owner"]) == (theirs["ref"], theirs["process_owner"])
    assert ours["metrics"] == theirs["metrics"]
    assert (ours["detail"], ours["figure"]) == (theirs["detail"], theirs["figure"])
    leadership = b.get(f"/api/versions/{b.version_id}/leadership")
    assert ours["metrics"]["handoffs"] == sum(p["handoffs"] for p in leadership["facts"]["phases"])
    s = leadership["summary"]
    assert (s["systems"], s["handoffs_manual"], s["handoffs"], s["off_system_steps"],
            s["no_record_steps"]) == (3, 2, 6, 1, 0)  # fmt: skip
    # The reference unit's own summary has no steps_differing.
    a = fx.arden
    arden = a.get(f"/api/versions/{a.version_id}/leadership")["summary"]
    assert arden["steps_differing"] is None
    arden_summary = next(f for f in returned(a)["findings"] if f["kind"] == "process_summary")
    assert "steps_differing" not in arden_summary["metrics"]


def test_10_a_step_with_no_time_is_left_out_and_said(fx: Fixture) -> None:
    b = fx.belmar
    with session_scope(b.client.app.state.sessions) as s:  # type: ignore[attr-defined]
        row = s.get(Element, b.steps["S-11"])
        assert row is not None
        row.work_min, row.wait_min = None, None
    [ours] = [f for f in returned(b)["findings"] if f["kind"] == "process_summary"]
    assert ours["metrics"]["work_min"] == 840 - 240 and ours["metrics"]["wait_min"] == 7200
    assert ours["detail"].endswith("Times recorded on 10 of 11 steps.")


def test_11_the_hand_offs_process_owner_is_offered_not_set(client: TestClient) -> None:
    file = packet("belmar")
    for pilot in file["pilots"]:
        if pilot["ref"] == "VS-01":
            pilot["process_owner"] = CM
    shown = preview(client, file).json()
    assert next(p for p in shown["pilots"] if p["ref"] == "VS-01")["process_owner"] == CM
    made = client.post("/api/engagements", json={
        "name": "Bid to contract renewal", "compass": {"handoff": file, "pilot_ref": "VS-01"},
    }).json()  # fmt: skip
    assert made["compass"]["process_owner"] == CM
    assert (made["process_owner"], made["process_owner_role_id"]) == ("", None)  # not set


def test_the_frontend_accountability_sample_matches_the_backend(fx: Fixture) -> None:
    """frontend/tests/fixtures/accountability_sample.json: Belmar's graph, SOP register,
    leadership view and comparison exactly as the backend sends them, so the screens are tested
    on the brief's own figures. Not a PRD baseline. Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    b = fx.belmar
    set_register(b)
    b.client.patch(f"/api/engagements/{b.engagement_id}",
                   json={"process_owner_role_id": b.roles[CM]})  # fmt: skip
    view = compare_and_class(fx)
    bundle = {
        "graph": b.get(f"/api/versions/{b.version_id}/graph"),
        "sop_register": b.get(f"/api/engagements/{b.engagement_id}/sop-register"),
        "leadership": b.get(f"/api/versions/{b.version_id}/leadership"),
        "comparison": view,
    }
    matches_baseline("accountability_sample.json", bundle, FRONTEND_FIXTURES)
