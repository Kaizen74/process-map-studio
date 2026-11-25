"""Who decides and who is accountable (PRD §3.20; DECISIONS 110): the brief's table, by rule."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.graph import GraphElement
from app.services import accountability as rules
from app.services import compass_return

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "G1_graph.json"
ROLES = {
    "sup": "Shift supervisor",
    "clc": "Certified load controller",
    "stn": "Station manager",
    "rro": "Regional roster owner",
    "cm": "Country manager",
    "rfc": "Regional finance controller",
    "com": "Commercial lead",
    "ramp": "Ramp agent",
}


def step(
    kind: str,
    *,
    lane: str,
    decider: str | None = None,
    a: tuple[tuple[str, bool], ...] = (),
    paper: str | None = None,
) -> GraphElement:
    template: dict[str, Any] = next(
        e for e in json.loads(GOLDEN.read_text("utf-8"))["elements"] if e["kind"] == "approval"
    )
    raci = [{"role_id": r, "letter": "A", "contested": c} for r, c in a]
    if kind == "activity":
        raci.append({"role_id": lane, "letter": "R", "contested": False})
    return GraphElement.model_validate({
        **template, "kind": kind, "lane_role_id": lane, "raci": raci,
        "decision": {**template["decision"], "decider_role_id": decider},
        "paper_decider": {"status": "named", "role_id": paper} if paper else None,
    })  # fmt: skip


S03 = step("approval", lane="sup", decider="sup", a=(("clc", False),), paper="clc")
S05 = step("approval", lane="stn", decider="stn", a=(("rro", True),), paper="rro")
S07 = step("decision", lane="cm", decider="cm", a=(("cm", False), ("rfc", False)))
S08 = step("decision", lane="com")
S02 = step("activity", lane="ramp")


def fields(e: GraphElement) -> dict[str, Any]:
    return compass_return.decision_fields(rules.rights(e, ROLES))


def test_the_three_roles_follow_the_brief_table() -> None:
    assert fields(S03) == {"on_paper": "Certified load controller",
                           "decided_by": "Shift supervisor",
                           "accountable": "Certified load controller"}  # fmt: skip
    assert fields(S05) == {"on_paper": "Regional roster owner", "decided_by": "Station manager",
                           "accountable": "Regional roster owner",
                           "accountable_contested": True}  # fmt: skip
    assert fields(S07) == {"decided_by": "Country manager",
                           "accountable": "Country manager / Regional finance controller",
                           "accountable_contested": True}  # fmt: skip
    assert fields(S08) == {"decided_by": "Commercial lead"}  # the lane decides; nobody holds A
    assert rules.rights(S02, ROLES) is None and fields(S02) == {}


def test_decides_versus_accountable_reads_as_the_compass_reads_it() -> None:
    split = {name: rules.rights(e, ROLES) for name, e in
             (("S03", S03), ("S05", S05), ("S07", S07), ("S08", S08))}  # fmt: skip
    assert {k for k, r in split.items() if r and r.split} == {"S03", "S05", "S07"}
    # Case and punctuation are ignored, as in the Compass.
    same = rules.Rights(on_paper="", decided_by="Shift supervisor", accountable="shift-supervisor",
                        contested=False)  # fmt: skip
    assert not same.split
    counts = rules.raci_counts([S03, S05, S07, S08, S02], ROLES)
    assert counts == rules.RaciCounts(decisions=4, paper_differs=2, split=3, contested=2)


def test_the_hint_only_asks_when_the_documents_name_someone_else() -> None:
    assert rules.paper_hint(S03, ROLES, has_different_role=False) == rules.PAPER_HINT
    assert rules.paper_hint(S03, ROLES, has_different_role=True) == ""  # D12 already there
    agrees = step("approval", lane="sup", decider="sup", paper="sup")
    assert rules.paper_hint(agrees, ROLES, has_different_role=False) == ""
    assert rules.paper_hint(S07, ROLES, has_different_role=False) == ""  # nothing on paper
