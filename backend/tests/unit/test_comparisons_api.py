"""Comparing countries: lining up the steps of two published maps, the differences, and classing
them (2026-11-13, Eric's brief §4.3-4.5 and acceptance tests 3, 4, 5 and 8; DECISIONS 98).
API_CONTRACT.md → Comparing countries. Mocked: Claude's suggestion is a canned answer."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import country_compare as rules
from tests.countries_fixture import PERSON, Countries, build, key_of, republish
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_roles_choose_remove import audit_actions
from tests.uploads import wait_for_jobs

APPROVE, LEGAL, CREDIT = (
    key_of("Approve the renewal price"),
    key_of("Legal review of terms"),
    key_of("Check the credit limit"),
)
DRAFT_PRICE, RECEIVE = key_of("Draft the renewal price"), key_of("Receive the renewal request")


@pytest.fixture()
def countries(client: TestClient) -> Countries:
    return build(client)


def said(response: Any) -> str:
    return str(response.json()["error"]["message"])


def compare(c: Countries) -> dict[str, Any]:
    made = c.client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": c.belmar},
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


def decide_pair(c: Countries, cid: str, ref: str | None, other: str | None, decision: str) -> Any:
    body = {"reference_key": ref, "other_key": other, "decision": decision}
    response = c.client.put(f"/api/comparisons/{cid}/pairs", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def confirm_proposals(c: Countries, view: dict[str, Any]) -> dict[str, Any]:
    for p in view["pairs"]:
        if p["status"] == "proposed":
            view = decide_pair(c, view["id"], p["reference_key"], p["other_key"], "confirmed")
    return view


def paired(c: Countries) -> dict[str, Any]:
    """The comparison with the obvious pairs confirmed and the two lone steps marked."""
    view = confirm_proposals(c, compare(c))
    decide_pair(c, view["id"], LEGAL, None, "only_reference")
    return dict(decide_pair(c, view["id"], None, CREDIT, "only_other"))


def by_kind(view: dict[str, Any]) -> dict[tuple[str, str | None, str | None], dict[str, Any]]:
    return {(d["kind"], d["reference_key"], d["other_key"]): d for d in view["differences"]}


# --- Choosing what to compare (acceptance test 8) ---------------------------------------------


def test_only_the_same_process_is_offered_and_compared(countries: Countries) -> None:
    c = countries
    alone = c.client.post("/api/engagements", json={"name": "Load control"}).json()
    offered = c.get(f"/api/engagements/{c.belmar}/comparison-candidates")
    assert [(o["engagement_id"], o["why"], o["published_label"]) for o in offered] == [
        (c.arden, "this map started from it", "v1.0")
    ]
    assert [
        o["engagement_id"] for o in c.get(f"/api/engagements/{c.arden}/comparison-candidates")
    ] == [c.belmar]
    different = c.client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": alone["id"]},
    )
    assert different.status_code == 409
    assert said(different) == (
        "These maps describe different processes (VS-01 and Load control). Only maps of the "
        "same process in two countries are compared."
    )
    same = c.client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": c.arden},
    )
    assert same.status_code == 422 and said(same) == "Choose two different engagements."


def test_a_draft_or_an_unpublished_map_is_never_compared(countries: Countries) -> None:
    c = countries
    with_draft = c.client.post(f"/api/versions/{c.belmar_version}/reopen")
    assert with_draft.status_code == 201, with_draft.text
    draft = with_draft.json()
    refused = c.client.post(
        "/api/comparisons",
        json={
            "reference_engagement_id": c.arden,
            "other_engagement_id": c.belmar,
            "other_version_id": draft["id"],
        },
    )
    assert refused.status_code == 409
    assert said(refused) == (
        f"Version {draft['label']} of MERIDIANBE VS-01 Bid to contract renewal is a draft. Only "
        "published maps are compared."
    )
    fresh = c.client.post(
        f"/api/engagements/{c.arden}/another-country", json={"country": "Caldera"}
    ).json()
    none = c.client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": fresh["id"]},
    )
    assert none.status_code == 409
    assert (
        said(none)
        == f"{fresh['name']} has no published version yet. Only published maps are compared."
    )


# --- Lining up the steps (acceptance test 3) --------------------------------------------------


def test_the_obvious_steps_are_proposed_with_their_reasons(countries: Countries) -> None:
    c = countries
    view = compare(c)
    again = c.client.post(
        "/api/comparisons",
        json={"reference_engagement_id": c.arden, "other_engagement_id": c.belmar},
    )
    assert again.status_code == 200 and again.json()["id"] == view["id"]  # the existing one
    assert (view["reference"]["country"], view["other"]["country"]) == ("Arden", "Belmar")
    # Named by country, so it reads right from either side (Eric, 2026-11-14).
    assert view["same_process"] == "Belmar's map started from Arden's"
    proposed = {(p["reference_key"], p["other_key"]): p["why"] for p in view["pairs"]}
    assert set(proposed) == {
        (k, k)
        for k in (
            RECEIVE,
            key_of("Build the bid solution"),
            DRAFT_PRICE,
            APPROVE,
            key_of("Send the renewal offer"),
        )
    }
    assert all(p["status"] == "proposed" for p in view["pairs"])
    assert proposed[(DRAFT_PRICE, DRAFT_PRICE)] == (
        "Same words: draft, price, renewal · same lane: Head of Pricing / Revenue Management · "
        "same kind of step · same phase: Price"
    )
    assert proposed[(APPROVE, APPROVE)].startswith("Same words: approve, price, renewal")
    assert view["differences"] == []  # nothing until Eric confirms
    codes = [s["code"] for s in view["steps"]["other"]]
    assert codes == [f"S-{n:02d}" for n in range(1, 7)]


def test_claude_suggests_pairs_between_existing_keys_only(countries: Countries) -> None:
    c = countries
    view = confirm_proposals(c, compare(c))
    started = c.client.post(f"/api/comparisons/{view['id']}/suggest")
    assert started.status_code == 202, started.text
    wait_for_jobs(c.client)
    job = c.get(f"/api/jobs/{started.json()['job_id']}")
    assert job["status"] == "done", job
    assert job["message"] == (
        "Claude suggested 1 pair for you to check. 1 suggestion was left out because it named a "
        "step that isn't unpaired on the map."
    )
    view = c.get(f"/api/comparisons/{view['id']}")
    [suggested] = [p for p in view["pairs"] if p["status"] == "suggested"]
    assert (suggested["reference_key"], suggested["other_key"]) == (LEGAL, CREDIT)
    assert view["suggest_job"]["status"] == "done"
    assert not any(d["reference_key"] == LEGAL for d in view["differences"])  # never applied
    # Eric refuses it by marking each step as only in its own country.
    decide_pair(c, view["id"], LEGAL, None, "only_reference")
    view = decide_pair(c, view["id"], None, CREDIT, "only_other")
    assert not [p for p in view["pairs"] if p["status"] == "suggested"]
    nothing = c.client.post(f"/api/comparisons/{view['id']}/suggest")
    assert nothing.status_code == 409
    assert said(nothing) == "Every step is already paired or decided: there is nothing to suggest."


def test_pair_decisions_are_checked_and_audited(countries: Countries) -> None:
    c = countries
    cid = compare(c)["id"]
    url = f"/api/comparisons/{cid}/pairs"
    bad = c.client.put(
        url, json={"reference_key": APPROVE, "other_key": None, "decision": "confirmed"}
    )
    assert bad.status_code == 422 and said(bad) == "Choose a step of each map."
    gone = c.client.put(
        url, json={"reference_key": "nope", "other_key": APPROVE, "decision": "confirmed"}
    )
    assert gone.status_code == 422 and said(gone) == "That step isn't on the compared map."
    odd = c.client.put(
        url, json={"reference_key": APPROVE, "other_key": APPROVE, "decision": "maybe"}
    )
    assert odd.status_code == 422
    # Choosing another step moves the decision: Arden's approval paired with Belmar's draft price.
    view = decide_pair(c, cid, APPROVE, DRAFT_PRICE, "confirmed")
    mine = [p for p in view["pairs"] if p["status"] == "confirmed"]
    assert [(p["reference_key"], p["other_key"]) for p in mine] == [(APPROVE, DRAFT_PRICE)]
    view = decide_pair(c, cid, APPROVE, APPROVE, "confirmed")
    mine = [p for p in view["pairs"] if p["status"] == "confirmed"]
    assert [(p["reference_key"], p["other_key"]) for p in mine] == [(APPROVE, APPROVE)]
    view = decide_pair(c, cid, APPROVE, None, "clear")
    assert not [p for p in view["pairs"] if p["status"] == "confirmed"]
    actions = [r["action"] for r in audit_actions(c.client, c.belmar)]
    assert {
        "Started country comparison",
        "Paired steps across countries",
        "Cleared a step pair",
    } <= set(actions)


def test_pairs_are_listed_in_process_order(countries: Countries) -> None:
    """Eric, 2026-11-13: the pairs follow the process, not the order they were confirmed in. A
    step only Belmar has sits after the step before it on Belmar's map."""
    c = countries
    view = paired(c)
    assert [(p["reference_key"], p["other_key"]) for p in view["pairs"]] == [
        (RECEIVE, RECEIVE),
        (key_of("Build the bid solution"), key_of("Build the bid solution")),
        (DRAFT_PRICE, DRAFT_PRICE),
        (APPROVE, APPROVE),
        (None, CREDIT),  # after Approve on Belmar's map
        (LEGAL, None),
        (key_of("Send the renewal offer"), key_of("Send the renewal offer")),
    ]


def test_differences_are_listed_in_process_order(countries: Countries) -> None:
    """Eric, 2026-11-13: the differences follow the same process order as the pairs, so
    Belmar's credit check sits after the price approval, before Arden's legal review."""
    view = paired(countries)
    assert [(d["kind"], d["reference_key"], d["other_key"]) for d in view["differences"]] == [
        ("work_time", DRAFT_PRICE, DRAFT_PRICE),
        ("who_does", APPROVE, APPROVE),
        ("who_decides", APPROVE, APPROVE),
        ("only_other", None, CREDIT),
        ("only_reference", LEGAL, None),
    ]


def test_confirmed_pairs_survive_a_republish_of_either_side(countries: Countries) -> None:
    c = countries
    view = paired(c)
    before = by_kind(view)
    newer = republish(c.client, c.belmar, c.belmar_version)
    stale = c.get(f"/api/comparisons/{view['id']}")
    assert stale["other"]["newer_version_label"] == "v2.0"  # "a newer version exists"
    assert stale["reference"]["newer_version_label"] is None
    refreshed = c.client.post(f"/api/comparisons/{view['id']}/refresh")
    assert refreshed.status_code == 200, refreshed.text
    after = refreshed.json()
    assert (after["other"]["version_id"], after["other"]["newer_version_label"]) == (newer, None)
    assert by_kind(after).keys() == before.keys()
    republish(c.client, c.arden, c.arden_version)
    again = c.client.post(f"/api/comparisons/{view['id']}/refresh").json()
    assert by_kind(again).keys() == before.keys()
    assert "Refreshed country comparison" in [
        r["action"] for r in audit_actions(c.client, c.belmar)
    ]


# --- The differences (acceptance test 4) ------------------------------------------------------


def test_the_differences_are_worked_out_by_rule(countries: Countries) -> None:
    c = countries
    view = paired(c)
    found = by_kind(view)
    assert set(found) == {
        ("who_does", APPROVE, APPROVE),
        ("who_decides", APPROVE, APPROVE),
        ("work_time", DRAFT_PRICE, DRAFT_PRICE),
        ("only_reference", LEGAL, None),
        ("only_other", None, CREDIT),
    }
    decides = found[("who_decides", APPROVE, APPROVE)]
    assert decides["topic"] == "decision_right"
    assert decides["title"] == (
        "Approve the renewal price: approved by Country manager in Belmar, by Regional finance "
        "controller in Arden"
    )
    assert (decides["reference_value"], decides["other_value"]) == (
        "Regional finance controller",
        "Country manager",
    )
    assert decides["grade"]["suggested"] == "indicated"
    assert decides["grade_reason"].startswith("Indicated: both steps are observed")
    time = found[("work_time", DRAFT_PRICE, DRAFT_PRICE)]
    assert time["figure"] == "60 min in Belmar vs 120 min in Arden (stated)"
    assert time["topic"] == "way_of_working"
    assert not [d for d in view["differences"] if d["reference_key"] == RECEIVE]  # 30 vs 25: none
    only_arden = found[("only_reference", LEGAL, None)]
    assert only_arden["title"] == (
        "Legal review of terms: only in Arden (Global Head, Commercial Excellence), not in Belmar"
    )
    assert only_arden["topic"] == "way_of_working"  # its lane exists in both countries
    assert only_arden["grade"]["suggested"] == "hypothesis"  # the other map may just be silent
    assert found[("only_other", None, CREDIT)]["topic"] == "role_presence"  # Country manager
    assert view["counts"] == {"open": 5, "kept": 0, "classed": 0, "dismissed": 0}
    text = json.dumps(view)
    assert not [p for p in PERSON.values() if p in text]  # no person's name, either side


def test_the_rules_on_their_own() -> None:
    c = rules.Countries("Arden", "Belmar", frozenset({"a"}), frozenset({"a", "b"}))
    base = rules.Step(
        key="k",
        code="S-01",
        label="Approve",
        kind="decision",
        lane="a",
        phase="P",
        order=1,
        mechanism="rule_based",
        work_min=10,
        wait_min=4,
        documents=1,
    )
    other = rules.Step(
        key="k",
        code="S-01",
        label="Approve",
        kind="decision",
        lane="a",
        phase="P",
        order=1,
        mechanism="judgment",
        work_min=14.9,
        wait_min=6,
        documents=0,
        discrepancies=(("X2", ("D12",)),),
    )
    found = {d.kind: d for d in rules.pair_differences(base, other, c)}
    assert set(found) == {"how_decided", "wait_time", "documented_vs_done"}  # 14.9 < 15
    assert found["how_decided"].title == (
        "Approve: decided by judgment in Belmar, by a fixed rule in Arden"
    )
    assert found["documented_vs_done"].topic == "decision_right"  # D12 on a decision
    assert "X2: different role" in found["documented_vs_done"].title
    assert found["wait_time"].suggested_grade == "hypothesis"  # Belmar's step has no source
    activity = rules.Step(
        key="k", code="", label="Approve", kind="activity", lane="a", phase="P", order=1
    )
    assert rules.pair_differences(base, activity, c)[0].kind in {"how_decided", "step_kind"}
    kinds = {d.kind: d.topic for d in rules.pair_differences(base, activity, c)}
    assert kinds["step_kind"] == "decision_right"
    lone = rules.only_difference(
        rules.Step(key="z", code="S-09", label="Z", kind="activity", lane="b", phase="", order=9),
        "other",
        c,
    )
    assert lone.topic == "role_presence"
    assert rules.discrepancy_topic("approval", ["D12"]) == "decision_right"
    assert rules.discrepancy_topic("activity", ["D12"]) == "way_of_working"
    assert rules.step_topic("decision") == "decision_right"


# --- Classing (acceptance test 5) -------------------------------------------------------------


def test_classing_gives_codes_that_are_never_reused(countries: Countries) -> None:
    c = countries
    view = paired(c)
    cid = view["id"]
    found = by_kind(view)

    def act(key: str, **body: Any) -> Any:
        return c.client.put(f"/api/comparisons/{cid}/differences/{key}", json=body)

    decides = found[("who_decides", APPROVE, APPROVE)]["key"]
    classed = act(
        decides,
        action="class",
        reason_class="inherited",
        reason_note="Belmar kept its pre-merger delegation of authority.",
    )
    assert classed.status_code == 200, classed.text
    assert (classed.json()["code"], classed.json()["status"]) == ("V1", "classed")
    time = found[("work_time", DRAFT_PRICE, DRAFT_PRICE)]["key"]
    assert act(time, action="keep").json()["code"] == "V2"  # kept without a reason
    performer = found[("who_does", APPROVE, APPROVE)]["key"]
    assert act(performer, action="dismiss").status_code == 422
    dismissed = act(performer, action="dismiss", note="The same decision as V1.")
    assert (dismissed.json()["code"], dismissed.json()["status"]) == (None, "dismissed")
    reopened = act(performer, action="reopen").json()
    assert (reopened["status"], reopened["code"]) == ("open", None)
    legal = found[("only_reference", LEGAL, None)]["key"]
    assert act(legal, action="class", reason_class="unknown").json()["code"] == "V3"
    again = act(decides, action="class", reason_class="chosen", reason_note="Agreed locally.")
    assert again.json()["code"] == "V1"  # a code stays with its difference
    assert act(performer, action="keep", grade="hypothesis").json()["code"] == "V4"
    # The checks on what Eric types.
    assert said(act(decides, action="class", reason_class="weather")) == (
        "Choose Required, Chosen, Inherited or Not known yet."
    )
    assert said(act(decides, action="class", reason_class="required")) == "Add one line saying why."
    hidden = act(
        decides,
        action="class",
        reason_class="chosen",
        reason_note=f"{PERSON['belmar']} decided it.",
    )
    assert hidden.status_code == 422
    assert said(hidden) == (
        "The reason contains a name from your list of names to hide. Use the role instead."
    )
    assert (
        act(decides, action="class", reason_class="chosen", reason_note="x" * 301).status_code
        == 422
    )
    assert act(decides, action="shrug").status_code == 422
    assert act(decides, action="keep", grade="certain").status_code == 422
    assert act("who_does|nope|nope", action="keep").status_code == 404
    graded = act(time, action="keep", grade="confirmed").json()["grade"]
    assert (graded["grade"], graded["suggested"], graded["chosen_by_owner"]) == (
        "confirmed",
        "indicated",
        True,
    )
    view = c.get(f"/api/comparisons/{cid}")
    assert view["counts"] == {"open": 1, "kept": 2, "classed": 2, "dismissed": 0}
    actions = {r["action"] for r in audit_actions(c.client, c.belmar)}
    assert {
        "Classed country difference",
        "Kept country difference",
        "Dismissed country difference",
        "Reopened country difference",
    } <= actions
    # The codes belong to Belmar's engagement, never to Arden's.
    listed = c.get(f"/api/engagements/{c.arden}/comparisons")
    assert [s["id"] for s in listed] == [cid]
    assert listed[0]["differences"] == view["counts"]


def test_a_difference_that_goes_away_keeps_its_code_aside(countries: Countries) -> None:
    c = countries
    view = paired(c)
    decides = by_kind(view)[("who_decides", APPROVE, APPROVE)]["key"]
    c.client.put(f"/api/comparisons/{view['id']}/differences/{decides}", json={"action": "keep"})
    after = decide_pair(c, view["id"], APPROVE, None, "clear")
    assert [(d["key"], d["code"]) for d in after["no_longer_found"]] == [(decides, "V1")]


def test_the_frontend_comparison_sample_matches_the_backend(countries: Countries) -> None:
    """frontend/tests/fixtures/comparison_sample.json: Belmar's candidates, the comparison with
    the obvious pairs confirmed, one difference classed and one kept, and the list of comparisons,
    exactly as the backend sends them. Not a PRD baseline. Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    c = countries
    view = paired(c)
    found = by_kind(view)
    url = f"/api/comparisons/{view['id']}/differences"
    decides = found[("who_decides", APPROVE, APPROVE)]["key"]
    c.client.put(
        f"{url}/{decides}",
        json={
            "action": "class",
            "reason_class": "inherited",
            "reason_note": "Belmar kept its pre-merger delegation.",
        },
    )
    c.client.put(
        f"{url}/{found[('work_time', DRAFT_PRICE, DRAFT_PRICE)]['key']}", json={"action": "keep"}
    )
    bundle = {
        "candidates": c.get(f"/api/engagements/{c.belmar}/comparison-candidates"),
        "comparison": c.get(f"/api/comparisons/{view['id']}"),
        "comparisons": c.get(f"/api/engagements/{c.belmar}/comparisons"),
    }
    matches_baseline("comparison_sample.json", bundle, FRONTEND_FIXTURES)
