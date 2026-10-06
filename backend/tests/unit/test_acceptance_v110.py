"""End-to-end proof on the fixture engagement (session 17, V4; PRD Appendix A.5, A.8, A.9 and
A.10), Claude mocked: the sources read (A.1-A.4 and the A.10 landscape interview), speakers mapped
to roles, Create draft map run through every stage, then each expected-outcome table checked row
by row through the API the app itself uses. Where a row is met by an earlier, more detailed test,
this file still checks it here so the proof reads in one place.

Known, logged exceptions (DECISIONS.md): A.5 "Issue load sheet … 5 min" is in no source, so the
map gives no work time (2026-09-27); A.8's reality gap is checked in G7 and the Analysis A tests.
"""

from __future__ import annotations

import json
from typing import Any

from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def get(d: Drafted, path: str, **params: str) -> Any:
    response = d.client.get(f"/api/{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def graph(d: Drafted, view: str | None = None) -> dict[str, Any]:
    return dict(get(d, f"versions/{d.version_id}/graph", **({"view": view} if view else {})))


def lines(g: dict[str, Any]) -> set[tuple[str, str, str, str, str]]:
    label = {e["id"]: e["label"] for e in g["elements"]}
    return {(label[x["from"]], label[x["to"]], x["kind"], x["label"], x["sequence_basis"])
            for x in g["edges"]}  # fmt: skip


def test_a5_every_element_its_lane_source_state_and_view(drafted: Drafted) -> None:
    g = graph(drafted)
    roles = {r["id"]: r["name"] for r in g["roles"]}
    found = {
        e["label"]: (e["kind"], roles.get(e["lane_role_id"] or "", ""), e["source_state"],
                     e["divergence_types"], e["view_membership"])
        for e in g["elements"] if e["kind"] not in {"start", "end"}
    }  # fmt: skip
    assert found == {
        "Draft load plan": ("activity", "Load controller", "corroborated", [], "both"),
        "Approve load plan": ("approval", "Load control lead", "documented_only", [],
                              "documented_only"),
        "Special loads OK?": ("decision", "Load controller", "corroborated", [], "both"),
        "Resolve or offload": ("activity", "Airline ops", "practiced_only", [], "done_only"),
        "Load and return LIR": ("activity", "Ramp", "contested", ["threshold"], "both"),
        "Deviation in limits?": ("decision", "Load controller", "contested", ["ownership"], "both"),
        "Approve deviation": ("approval", "Captain", "practiced_only", [], "done_only"),
        "Issue load sheet": ("activity", "Load controller", "corroborated", [], "both"),
        "Busy wave?": ("decision", "Load controller", "practiced_only", [], "done_only"),
        "Read report at aircraft": ("activity", "Load controller", "practiced_only", [],
                                    "done_only"),
    }  # fmt: skip
    by = {e["label"]: e for e in g["elements"]}
    assert by["Draft load plan"]["time"]["work_min"] == 20
    assert by["Special loads OK?"]["decision"]["mechanism"] == "rule_based"
    assert by["Busy wave?"]["decision"]["mechanism"] == "rule_based"  # the condition is stated
    deviation = {
        (roles[r["role_id"]], r["letter"], r["contested"])
        for r in by["Deviation in limits?"]["raci"]
    }
    assert {("Captain", "A", True), ("Load control lead", "A", True)} <= deviation
    key = {c["text"] for e in g["elements"] for c in e["constraints"] if c["is_key"]}
    assert len(key) >= 3  # late notification, paper re-keying, container shortage (A.5)
    lint = get(drafted, f"versions/{drafted.version_id}/lint")
    assert lint["failures"] == []  # A.5: zero failures
    assert "Priya" not in json.dumps(g)


def test_a9_the_as_done_and_as_documented_paths(drafted: Drafted) -> None:
    done, documented = graph(drafted, "done"), graph(drafted, "documented")
    # As done: Draft load plan → Special loads OK? → Load and return LIR → Busy wave? (Yes → Read
    # report at aircraft) → Deviation in limits? → Issue load sheet, the exception branches of
    # A.5, and no Approve load plan and no "not described" connector (the order is stated).
    assert "Approve load plan" not in {e["label"] for e in done["elements"]}
    assert lines(done) == {
        ("Flight scheduled", "Draft load plan", "sequence", "", "explicit_order"),
        ("Draft load plan", "Special loads OK?", "sequence", "", "explicit_order"),
        ("Special loads OK?", "Load and return LIR", "yes", "Yes", "explicit_order"),
        ("Special loads OK?", "Resolve or offload", "no", "No", "explicit_order"),
        ("Resolve or offload", "Draft load plan", "rework", "Re-plan", "explicit_order"),
        ("Load and return LIR", "Busy wave?", "sequence", "", "narration_order"),
        ("Busy wave?", "Read report at aircraft", "yes", "Yes", "explicit_order"),
        ("Busy wave?", "Deviation in limits?", "no", "No", "explicit_order"),
        ("Read report at aircraft", "Deviation in limits?", "sequence", "", "narration_order"),
        ("Deviation in limits?", "Issue load sheet", "yes", "Within limits", "explicit_order"),
        ("Deviation in limits?", "Approve deviation", "no", "Outside limits", "explicit_order"),
        ("Approve deviation", "Issue load sheet", "approve", "Accept", "explicit_order"),
        ("Approve deviation", "Load and return LIR", "rework", "Re-trim", "explicit_order"),
        ("Issue load sheet", "Final load sheet issued", "sequence", "", "explicit_order"),
        # A.10: the hand-overs stitched across the two interviews.
        ("Draft load plan", "Load and return LIR", "sequence", "", "dependency"),
        ("Load and return LIR", "Deviation in limits?", "sequence", "", "dependency"),
    }  # fmt: skip
    assert not any(x["kind"] == "gap" for x in done["edges"])
    # As documented: Draft load plan → Approve load plan → Special loads OK? → Load and return
    # LIR → Deviation in limits? → Issue load sheet.
    assert lines(documented) == {
        ("Flight scheduled", "Draft load plan", "sequence", "", "explicit_order"),
        ("Draft load plan", "Approve load plan", "sequence", "", "document_order"),
        ("Approve load plan", "Special loads OK?", "approve", "Approve", "explicit_order"),
        ("Approve load plan", "Draft load plan", "reject", "Rework", "explicit_order"),
        ("Special loads OK?", "Load and return LIR", "yes", "Yes", "explicit_order"),
        ("Load and return LIR", "Deviation in limits?", "sequence", "", "dependency"),
        ("Deviation in limits?", "Issue load sheet", "yes", "Within limits", "explicit_order"),
        ("Issue load sheet", "Final load sheet issued", "sequence", "", "explicit_order"),
        ("Draft load plan", "Load and return LIR", "sequence", "", "dependency"),
    }  # fmt: skip
    # Variants: time and decider differ between the views.
    by = {e["label"]: e for e in graph(drafted)["elements"]}
    assert by["Load and return LIR"]["variants"] == {
        "done": {"time": "Up to fifteen minutes' wait for the report"},
        "documented": {"time": "Within 10 minutes of loading completion"},
    }
    assert by["Deviation in limits?"]["variants"] == {
        "done": {"owner": "Captain"}, "documented": {"owner": "Load control lead"}}  # fmt: skip
    # Provenance: every As done step carries the quotes and question IDs that produced it.
    for e in done["elements"]:
        if e["kind"] in {"start", "end"}:
            continue
        answers = get(drafted, f"elements/{e['id']}")["answers"]
        assert answers and all(a["quote"] and a["question_id"] for a in answers), e["label"]


def test_a8_work_types_know_how_story_and_coverage(drafted: Drafted) -> None:
    by = {e["label"]: e for e in graph(drafted)["elements"]}
    assert {label: by[label]["work_type"] for label in (
        "Special loads OK?", "Draft load plan", "Deviation in limits?", "Issue load sheet",
        "Busy wave?")} == {
        "Special loads OK?": "clear", "Draft load plan": "complicated",
        "Deviation in limits?": "complex", "Issue load sheet": "clear",
        "Busy wave?": "not_classified"}  # fmt: skip
    deviation = get(drafted, f"elements/{by['Deviation in limits?']['id']}")
    assert [c["anchor"] for c in deviation["work_type_cues"]] == ["29:48", "29:48"]
    assert deviation["ai_flag"] is None  # complex work is never an automation candidate
    assert deviation["know_how"]["knowledge_risk"] == "high"
    special = get(drafted, f"elements/{by['Special loads OK?']['id']}")
    assert special["know_how"]["knowledge_risk"] == "low"
    [story] = deviation["stories"]
    assert (story["fragment_type"], story["signifiers"], story["frequency"]) == (
        "went_badly", ["Firefighting"], "maybe once a month")  # fmt: skip
    terms = [t["term"] for t in get(drafted, f"versions/{drafted.version_id}/glossary")]
    assert terms == ["re-trim", "wave", "forward hold"]
    coverage = get(drafted, f"versions/{drafted.version_id}/coverage")["dimensions"]
    assert (coverage["kpis"]["status"], coverage["stories"]["status"],
            coverage["official_vs_lived"]["status"]) == ("missing", "thin", "covered")  # fmt: skip


def test_a10_stitching_capability_notes_and_the_probe(drafted: Drafted) -> None:
    g = graph(drafted)
    label = {e["id"]: e["label"] for e in g["elements"]}
    stitched = {(label[x["from"]], label[x["to"]], x["information_payload"], x["view_membership"])
                for x in g["edges"] if x["sequence_basis"] == "dependency"}  # fmt: skip
    assert stitched == {
        ("Draft load plan", "Load and return LIR", "preliminary load plan", "both"),
        ("Load and return LIR", "Deviation in limits?", "loading report", "both"),
    }
    notes = get(drafted, f"versions/{drafted.version_id}/capability-notes")
    assert [(n["kind"], n["dimension"], n["cause_type"]) for n in notes] == [
        ("strength", "skillset", None),
        ("weakness", "systems", "system_fragmentation"),
    ]
    lir = next(e for e in g["elements"] if e["label"] == "Load and return LIR")
    assert any(c["cause_type"] == "system_fragmentation" and "gets lost" in c["text"]
               for c in lir["constraints"])  # fmt: skip
    probes = get(drafted, f"versions/{drafted.version_id}/coverage")["probes"]
    assert any("it gets lost or arrives late" in p["question"] and p["question_id"] == "F2"
               for p in probes)  # fmt: skip


def test_a10_landscape_answers_join_practice_steps_without_duplication(drafted: Drafted) -> None:
    """Criterion 70 on the fixture (C8; the nesting itself is proved with a crafted case, Decision
    C, because A.10 names no team-level activity of its own): the landscape interview's answers
    (L3, L6) give the Ramp its lane, the interfaces (the stitched hand-overs) and the lane
    boundary on the practice step they describe; they add no step of their own, so no step is
    duplicated and the map keeps one level."""
    g = graph(drafted)
    labels = [e["label"] for e in g["elements"]]
    assert len(labels) == len(set(labels))
    lanes = {r["id"]: r["name"] for r in g["roles"]}
    lir = next(e for e in g["elements"] if e["label"] == "Load and return LIR")
    assert lanes[lir["lane_role_id"]] == "Ramp"
    assert all(e["level"] is None and e["parent_element_id"] is None for e in g["elements"])
    # Its decision rights stay where they were: the one Responsible is the Ramp; the load
    # controller, whom the landscape interview also names on the step, is Consulted (C8).
    found = get(drafted, f"versions/{drafted.version_id}/lane-boundaries")
    assert [(f["label"], f["responsible"], f["consulted"]) for f in found] == [
        ("Load and return LIR", "Ramp", ["Load controller"])]  # fmt: skip
