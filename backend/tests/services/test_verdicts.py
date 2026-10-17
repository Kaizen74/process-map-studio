"""Locations, impact classes and suggested verdicts (PRD §3.17.4-3.17.6; P13a-3b): the rules A.12
doesn't reach, table-driven. Pure: no database, no AI."""

from __future__ import annotations

import dataclasses

from app.services import discrepancies as rules
from app.services import verdicts
from app.services.discrepancies import Facts, IntentOnStep, Line, Measure
from tests.services.test_discrepancies import APPROVE, LINES, LOAD, PLAN, step, world


def located(facts: Facts) -> list[verdicts.Group]:
    return verdicts.group([f for f in rules.detect(facts) if f.shown], facts)


def at(facts: Facts, key: str) -> verdicts.Group:
    return next(g for g in located(facts) if key in g.keys and g.kind != "design")


def test_runs_of_added_steps_share_one_location_and_a_design_gap_keeps_its_own() -> None:
    a = step("walk", 3, in_documented=False, described_in=1)
    b = step("read", 4, in_documented=False, described_in=1)
    lines = [*LINES, Line("plan", "walk", "sequence"), Line("walk", "read", "sequence")]
    target = IntentOnStep("i1", "target", ("plan",), "lead_time_min", "at_least", 120.0,
                          documented=90.0, documented_meets=False)  # fmt: skip
    facts = world(PLAN, APPROVE, LOAD, a, b, done_lines=lines, intents=[target],
                  variants=[60, 40])  # fmt: skip
    groups = {g.location_key: g for g in located(facts)}
    assert groups["run:walk+read"].types == ["D2"]
    assert [g.kind for g in groups.values() if "plan" in g.keys] == ["design"]
    assert groups["process:D9:process"].kind == "process"
    assert verdicts.impact(groups["process:D9:process"], facts) is None
    assert verdicts.verdict(groups["process:D9:process"], facts) == (None, "")


def test_impact_classes() -> None:
    # A risk flag makes any discrepancy a control exposure.
    owner = dataclasses.replace(LOAD, documented_owner="Lead", done_owner="Captain")
    assert verdicts.impact(at(world(PLAN, APPROVE, owner), "load"), world()) == "workaround"
    flagged = dataclasses.replace(owner, risk_flag="safety")
    facts = world(PLAN, APPROVE, flagged)
    assert verdicts.impact(at(facts, "load"), facts) == "control_exposure"
    # A wait on the usual route is a time impact; off it, without hours, a workaround.
    waiting = dataclasses.replace(LOAD, usual_route=True, per_month=100,
                                  wait_before=Measure(12, 20, 100))  # fmt: skip
    facts = world(PLAN, APPROVE, waiting)
    group = at(facts, "load")
    assert (verdicts.impact(group, facts), verdicts.hours(group, facts)) == ("time_impact", 20.0)
    # Measured added work off the usual route is a capacity drain.
    added = step("check", 3, in_documented=False, recorded=True, cases=30, per_month=40,
                 time=Measure(15, 20, 30))  # fmt: skip
    facts = world(PLAN, APPROVE, LOAD, added)
    assert verdicts.impact(at(facts, "check"), facts) == "capacity_drain"
    # A design gap on a control objective is a control exposure.
    objective = IntentOnStep("i1", "control_objective", ("approve",))
    rule = rules.DesignConflict("c1", "i1", ("approve",), "The policy needs two approvers.")
    facts = world(intents=[objective], conflicts=[rule])
    [design] = [g for g in located(facts) if g.kind == "design"]
    assert verdicts.impact(design, facts) == "control_exposure"
    assert verdicts.verdict(design, facts)[0] == "rewrite"


def test_verdicts_and_their_reasons() -> None:
    unrecorded = dataclasses.replace(APPROVE, recorded=False)
    objective = IntentOnStep("i1", "control_objective", ("approve",))
    facts = world(PLAN, unrecorded, LOAD, intents=[objective])
    assert verdicts.verdict(at(facts, "approve"), facts) == ("correct", verdicts.CORRECT_CONTROL)
    facts = world(PLAN, unrecorded, LOAD)
    assert verdicts.verdict(at(facts, "approve"), facts) == ("ask", verdicts.ASK_NO_INTENT)
    reason = dataclasses.replace(unrecorded, stated_reason=True)
    facts = world(PLAN, reason, LOAD)
    assert verdicts.verdict(at(facts, "approve"), facts) == ("ask", verdicts.ASK_STATED)


def test_codes_go_by_impact_then_hours_then_process_order() -> None:
    owner = dataclasses.replace(PLAN, documented_owner="Lead", done_owner="Captain")
    unrecorded = dataclasses.replace(APPROVE, recorded=False)
    small = dataclasses.replace(LOAD, usual_route=True, per_month=10, wait_before=Measure(6, 9, 50))
    big = step("ship", 3, usual_route=True, recorded=True, cases=100, per_month=100,
               wait_before=Measure(30, 40, 100))  # fmt: skip
    facts = world(owner, unrecorded, small, big)
    groups = [g for g in located(facts) if g.kind != "process"]
    impacts = {g.location_key: verdicts.impact(g, facts) for g in groups}
    order = [g.location_key for g in verdicts.code_order(groups, facts, impacts)]
    assert order == ["step:approve", "step:ship", "step:load", "step:plan"]
