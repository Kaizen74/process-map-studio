"""Adding a missing step and editing lines (API_CONTRACT.md → Review; PRD §5.7.6, §6.3 P6 tests
"add-step placement" and "O add-step without passage refused"). Illustrative Appendix A
engagement, Claude mocked."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update

from app.db import session_scope
from app.repositories.tables import MapVersion
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_edit import element, role

__all__ = ["drafted"]


def add(d: Drafted, **fields: Any) -> Any:
    body = {"kind": "activity", "label": "Check fuel figures", "provenance": "O",
            "lane_role_id": role(d, "Load controller"),
            "after_element_id": d.ids["Draft load plan"]} | fields  # fmt: skip
    return d.client.post(f"/api/versions/{d.version_id}/elements", json=body)


def passage(d: Drafted, label: str = "Draft load plan") -> str:
    return str(next(c["segment_id"] for c in element(d, label)["evidence"] if c["segment_id"]))


def graph(d: Drafted) -> dict[str, Any]:
    return dict(d.client.get(f"/api/versions/{d.version_id}/graph").json())


def lines(d: Drafted) -> set[tuple[str, str, str, str]]:
    g = graph(d)
    names = {e["id"]: e["label"] for e in g["elements"]}
    return {(names[e["from"]], names[e["to"]], e["kind"], e["label"]) for e in g["edges"]}


def lint_rules(d: Drafted) -> list[str]:
    report = d.client.get(f"/api/versions/{d.version_id}/lint").json()
    return [f["rule"] for f in report["failures"]]


def test_an_observed_step_goes_in_after_the_chosen_step(drafted: Drafted) -> None:
    before = lines(drafted)
    response = add(drafted, segment_ids=[passage(drafted)])
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["review_status"], body["provenance"], body["source_state"]) == (
        "added", "O", "not_assessed")  # fmt: skip
    assert body["confidence"] is None and body["phase_name"] == "Plan"
    [card] = [c for c in body["evidence"] if c["segment_id"]]
    assert (card["stance"], card["verified"], card["anchor"]) == ("supports", True, "06:40")
    assert [(r["role_name"], r["letter"]) for r in body["raci"]] == [
        ("Load controller", "R"), ("Load controller", "A")]  # fmt: skip
    after = lines(drafted)
    assert ("Draft load plan", "Approve load plan", "sequence", "") not in after
    assert {("Draft load plan", "Check fuel figures", "sequence", ""),
            ("Check fuel figures", "Approve load plan", "sequence", "")} <= after  # fmt: skip
    assert len(after) == len(before) + 1
    assert lint_rules(drafted) == []
    layout = drafted.client.get(f"/api/versions/{drafted.version_id}/layout").json()
    assert body["id"] in [n["id"] for n in layout["nodes"]]
    assert drafted.audit()[0]["action"] == "Added step"


def test_an_observed_step_needs_a_passage(drafted: Drafted) -> None:
    response = add(drafted)
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "VALIDATION",
        "message": "Pick the passage this step comes from.",
        "details": {"field": "segment_ids", "request_id": response.headers["X-Request-ID"]},
    }
    assert add(drafted, segment_ids=["nope"]).json()["error"]["details"]["field"] == "segment_ids"
    assert "Check fuel figures" not in {e["label"] for e in graph(drafted)["elements"]}


def test_a_recommended_step_needs_a_reference_and_inferred_is_refused(drafted: Drafted) -> None:
    assert add(drafted, provenance="R").json()["error"]["details"]["field"] == "r_reference"
    inferred = add(drafted, provenance="I", segment_ids=[passage(drafted)])
    assert inferred.json()["error"]["message"] == (
        "Choose Observed (with a passage) or Recommended (with a reference)."
    )
    body = add(drafted, provenance="R", r_reference="IATA AHM 560, section 2").json()
    assert (body["provenance"], body["r_reference"]) == ("R", "IATA AHM 560, section 2")
    assert [c for c in body["evidence"] if c["segment_id"]] == []


def test_the_field_rules_apply(drafted: Drafted) -> None:
    end = add(drafted, after_element_id=drafted.ids["Final load sheet issued"])
    assert end.json()["error"]["details"]["field"] == "after_element_id"
    named = add(drafted, label="Ask Priya Nair", segment_ids=[passage(drafted)])
    assert named.json()["error"]["details"]["field"] == "label" and "Priya" not in named.text
    undecided = add(drafted, kind="decision", mechanism="none", segment_ids=[passage(drafted)])
    assert undecided.json()["error"]["details"]["field"] == "mechanism"


def test_a_new_decision_gets_its_exits_labelled_with_lines(drafted: Drafted) -> None:
    body = add(drafted, kind="decision", label="Weight within limits?", segment_ids=[
        passage(drafted, "Load and return LIR")],
        after_element_id=drafted.ids["Load and return LIR"]).json()  # fmt: skip
    new = body["id"]
    assert body["decision"]["mechanism"] == "judgment"
    assert "L4" in lint_rules(drafted)  # one unlabelled exit so far
    exit_line = next(e for e in graph(drafted)["edges"] if e["from"] == new)
    url = f"/api/versions/{drafted.version_id}/edges"
    unlabelled = drafted.client.patch(f"{url}/{exit_line['id']}", json={"kind": "yes"})
    assert unlabelled.status_code == 422
    assert unlabelled.json()["error"]["message"] == (
        "Every exit of a decision or approval needs a label."
    )
    changed = drafted.client.patch(f"{url}/{exit_line['id']}", json={"kind": "yes", "label": "Yes"})
    assert changed.json() == exit_line | {"kind": "yes", "label": "Yes"}
    created = drafted.client.post(url, json={"from": new, "to": drafted.ids["Resolve or offload"],
                                             "kind": "no", "label": "No"})  # fmt: skip
    assert created.status_code == 201
    assert lint_rules(drafted) == []
    assert [r["action"] for r in drafted.audit()[:2]] == ["Added line", "Changed line"]
    assert drafted.client.delete(f"{url}/{created.json()['id']}").status_code == 204
    assert drafted.audit()[0]["action"] == "Removed line"
    assert "L4" in lint_rules(drafted)


def test_line_rules(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/edges"
    ids = drafted.ids
    cases = [
        ({"from": ids["Draft load plan"], "to": ids["Draft load plan"]}, "to"),
        ({"from": ids["Draft load plan"], "to": ids["Flight scheduled"]}, "to"),
        ({"from": ids["Final load sheet issued"], "to": ids["Draft load plan"]}, "to"),
        ({"from": ids["Draft load plan"], "to": "nope"}, "from"),
        ({"from": ids["Draft load plan"], "to": ids["Issue load sheet"], "kind": "maybe"}, "kind"),
        ({"from": ids["Draft load plan"], "to": ids["Approve load plan"]}, "to"),  # already joined
        ({"from": ids["Draft load plan"], "to": ids["Issue load sheet"],
          "label": "Tell Priya Nair"}, "label"),
        ({"from": ids["Draft load plan"], "to": ids["Issue load sheet"], "label": "x" * 61},
         "label"),
    ]  # fmt: skip
    for body, where in cases:
        response = drafted.client.post(url, json={"kind": "sequence"} | body)
        assert response.status_code == 422, body
        assert response.json()["error"]["details"]["field"] == where, body
    assert drafted.client.delete(f"{url}/nope").json()["error"]["message"] == (
        "That line doesn't exist."
    )


def test_a_published_version_cant_change(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        session.execute(
            update(MapVersion).where(MapVersion.id == drafted.version_id).values(state="published")
        )
    assert add(drafted, segment_ids=[passage(drafted)]).status_code == 409
    edge = graph(drafted)["edges"][0]
    url = f"/api/versions/{drafted.version_id}/edges/{edge['id']}"
    assert drafted.client.delete(url).status_code == 409
    assert drafted.client.post("/api/versions/nope/elements", json={
        "kind": "activity", "label": "x", "lane_role_id": "r", "after_element_id": "e",
        "provenance": "O"}).status_code == 404  # fmt: skip
