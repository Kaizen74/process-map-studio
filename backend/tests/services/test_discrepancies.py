"""The discrepancy engine's rules (PRD §3.17.2-3.17.3; P13a-3a), table-driven: each of the fourteen
types detected, and not detected where the PRD says it never is (including silence). Pure: no
database, no AI."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.services import discrepancies as rules
from app.services.discrepancies import Facts, HiddenWork, IntentOnStep, Line, Measure, StepFacts

MEASURED, STATED = "measured", "stated"


def step(key: str, order: int = 0, **fields: Any) -> StepFacts:
    base: dict[str, Any] = {"key": key, "element_id": f"e-{key}", "label": key.title(),
                            "kind": "activity", "order": order, "in_done": True,
                            "in_documented": True}  # fmt: skip
    return StepFacts(**(base | fields))


def found(facts: Facts, kind: str) -> list[rules.Found]:
    return [f for f in rules.detect(facts) if f.type == kind]


def one(facts: Facts, kind: str) -> rules.Found:
    [f] = found(facts, kind)
    return f


# A small documented process: plan → approve → load, every case recorded unless a test says so.
PLAN = step("plan", 0, recorded=True, cases=100)
APPROVE = step("approve", 1, kind="approval", recorded=True, cases=100)
LOAD = step("load", 2, recorded=True, cases=100)
LINES = [Line("plan", "approve", "sequence"), Line("approve", "load", "sequence")]


def world(*steps: StepFacts, **fields: Any) -> Facts:
    base: dict[str, Any] = {
        "steps": steps or (PLAN, APPROVE, LOAD),
        "done_lines": LINES,
        "documented_lines": LINES,
        "total_cases": 100,
        "interviews": 2,
    }
    return Facts(**(base | fields))


# --- D1 skipped step ----------------------------------------------------------------------------


def test_d1_from_the_log_skipping_the_step() -> None:
    skipped = dataclasses.replace(APPROVE, cases=90, reach_next=100, skipped=10)
    f = one(world(PLAN, skipped, LOAD), "D1")
    assert (f.keys, f.delta.label, f.delta.text, f.incidence, f.control) == (
        ("approve",), MEASURED, "10% of cases skip it", 0.1, True)  # fmt: skip


def test_d1_never_recorded_with_no_lived_account() -> None:
    unrecorded = dataclasses.replace(APPROVE, recorded=False, cases=0)
    f = one(world(PLAN, unrecorded, LOAD), "D1")
    assert (f.delta.text, f.incidence, f.cases, f.detail["basis"]) == (
        "never recorded; 100% of cases", 1.0, 100, "b")  # fmt: skip


def test_d1_stated_as_not_done() -> None:
    f = one(world(dataclasses.replace(APPROVE, not_done_quotes=1)), "D1")
    assert (f.delta.label, f.delta.text) == (STATED, "stated in 1 of 2 interviews")


@pytest.mark.parametrize(
    "changed",
    [
        # Silence alone: no log, no lived account (constraint 4) → a question, never D1.
        dataclasses.replace(APPROVE, recorded=None, cases=0),
        # Unrecorded but a lived account describes it (offline work, not a skip).
        dataclasses.replace(APPROVE, recorded=False, lived_accounts=1),
        # Below 5% of the cases reaching the next step.
        dataclasses.replace(APPROVE, reach_next=100, skipped=4),
        # Too few cases to say.
        dataclasses.replace(APPROVE, reach_next=4, skipped=4),
        # Not a documented step.
        dataclasses.replace(APPROVE, in_documented=False, recorded=False),
    ],
)
def test_d1_is_never_detected_from_silence_or_too_little(changed: StepFacts) -> None:
    assert found(world(PLAN, changed, LOAD), "D1") == []


def test_without_a_log_unrecorded_silence_is_not_skipped() -> None:
    facts = world(PLAN, dataclasses.replace(APPROVE, recorded=False), LOAD, total_cases=0)
    assert found(facts, "D1") == [] and found(facts, "D11") == []


# --- D2 added step ------------------------------------------------------------------------------


def test_d2_described_or_measured_and_hidden_work() -> None:
    added = step("walk", 3, in_documented=False, described_in=1)
    recorded = step("check", 4, in_documented=False, recorded=True, cases=30)
    facts = world(PLAN, APPROVE, LOAD, added, recorded,
                  hidden=[HiddenWork("Override", 12), HiddenWork("Rare", 4)])  # fmt: skip
    d2 = {f.keys: f for f in found(facts, "D2")}
    assert d2[("walk",)].delta.text == "described in 1 of 2 interviews"
    assert (d2[("check",)].delta.text, d2[("check",)].incidence) == ("30% of cases", 0.3)
    assert d2[("activity:Override",)].delta.text == "12% of cases"
    assert ("activity:Rare",) not in d2  # fewer than 5 cases
    assert found(world(), "D2") == []  # documented steps are never added


# --- D3 reordered -------------------------------------------------------------------------------


def test_d3_opposite_order_and_the_logs_order() -> None:
    done = [Line("approve", "plan", "sequence"), Line("plan", "load", "sequence")]
    f = one(world(done_lines=done), "D3")
    assert f.keys == ("approve", "plan")
    narrated = [Line("approve", "plan", "sequence", "narration_order")]
    assert found(world(done_lines=narrated), "D3") == []  # narration alone never counts
    system = one(world(contradictions={"load": "The log records Load before Approve."}), "D3")
    assert (system.keys, system.delta.label) == (("load",), MEASURED)


# --- D4 loop or rework --------------------------------------------------------------------------


def test_d4_measured_rework_and_described_loops() -> None:
    reworked = dataclasses.replace(PLAN, rework_cases=18)
    f = one(world(reworked, APPROVE, LOAD), "D4")
    assert (f.delta.text, f.incidence, f.shown) == ("rework in 18% of cases", 0.18, True)
    assert found(world(dataclasses.replace(PLAN, rework_cases=9), APPROVE, LOAD), "D4") == []
    loop = [*LINES, Line("load", "plan", "rework")]
    # With a log, a described loop takes the measured share: unseen in the log, not drawn.
    unseen = one(world(done_lines=loop), "D4")
    assert (unseen.incidence, unseen.shown) == (0.0, False)
    no_log = world(dataclasses.replace(PLAN, recorded=None), APPROVE, LOAD, done_lines=loop)
    assert one(no_log, "D4").delta.text == "a loop back is described"


# --- D5 control bypassed and D11 no record ------------------------------------------------------


def test_d5_a_recorded_control_routed_around() -> None:
    bypassed = dataclasses.replace(APPROVE, cases=80, reach_next=100, skipped=20)
    f = one(world(PLAN, bypassed, LOAD), "D5")
    assert (f.control, f.incidence, f.delta.text) == (True, 0.2, "20% of cases go round Approve")
    # Not a control (an activity with no flag and no control objective): D1 only.
    plain = dataclasses.replace(LOAD, cases=80, reach_next=100, skipped=20)
    assert found(world(PLAN, APPROVE, plain), "D5") == []


def test_d11_a_documented_control_never_recorded() -> None:
    unrecorded = dataclasses.replace(APPROVE, recorded=False, cases=0)
    f = one(world(PLAN, unrecorded, LOAD), "D11")
    assert (f.control, f.incidence, f.cases) == (True, 1.0, 100)
    assert found(world(PLAN, unrecorded, LOAD), "D5") == []  # unseen, so not "routed around"
    supported = dataclasses.replace(unrecorded, artefact_support=True)
    assert found(world(PLAN, supported, LOAD), "D11") == []
    # An added approval is not a documented control (§3.17.4).
    added = dataclasses.replace(unrecorded, in_documented=False)
    assert found(world(PLAN, added, LOAD), "D11") == []
    # A step covered by a confirmed control objective, or with a risk flag, is a control.
    objective = IntentOnStep("i1", "control_objective", ("load",))
    unrecorded_load = dataclasses.replace(LOAD, recorded=False)
    assert found(world(PLAN, APPROVE, unrecorded_load, intents=[objective]), "D11")
    flagged = dataclasses.replace(unrecorded_load, risk_flag="safety")
    assert found(world(PLAN, APPROVE, flagged), "D11")


# --- D6 off-system ------------------------------------------------------------------------------


def test_d6_unrecorded_steps_in_line_between_recorded_ones() -> None:
    walk = step("walk", 3, in_documented=False, recorded=False, described_in=1, tools=("sheet",))
    read = step("read", 4, in_documented=False, recorded=False, described_in=1)
    lines = [Line("plan", "walk", "sequence"), Line("walk", "read", "yes"),
             Line("read", "load", "sequence"), Line("plan", "load", "sequence")]  # fmt: skip
    f = one(world(PLAN, walk, read, LOAD, done_lines=lines), "D6")
    assert f.keys == ("walk", "read")  # one run, one finding
    assert f.delta.text == "described in 1 of 2 interviews; no system record; tool “sheet”"


def test_d6_not_on_a_decisions_exception_branch() -> None:
    check = step("check", 1, kind="decision", recorded=True, cases=100)
    fix = step("fix", 2, in_documented=False, recorded=False, described_in=1)
    lines = [Line("plan", "check", "sequence"), Line("check", "fix", "no"),
             Line("fix", "load", "sequence"), Line("check", "load", "yes")]  # fmt: skip
    assert found(world(PLAN, check, fix, LOAD, done_lines=lines), "D6") == []


def test_d6_from_an_unofficial_tool_alone() -> None:
    f = one(world(dataclasses.replace(LOAD, tools=("spreadsheet",))), "D6")
    assert f.detail["tool"] == "spreadsheet"


# --- D7 takes longer and D8 waiting --------------------------------------------------------------


def test_d7_more_than_half_as_long_again() -> None:
    slow = dataclasses.replace(LOAD, documented_min=10, time=Measure(16, 25, 100))
    f = one(world(PLAN, APPROVE, slow), "D7")
    assert (f.delta.value, f.delta.label, f.delta.text) == (
        6,
        MEASURED,
        f"+6 min a case ({rules.TIMES}1.6)",
    )
    within = dataclasses.replace(slow, time=Measure(14, 25, 100))  # +40%: within 50% (A.11)
    assert found(world(PLAN, APPROVE, within), "D7") == []
    stated = dataclasses.replace(LOAD, documented_min=10, done_min=20, recorded=None)
    assert one(world(PLAN, APPROVE, stated), "D7").delta.label == STATED
    few = dataclasses.replace(slow, time=Measure(16, 25, 4), done_min=None)
    assert found(world(PLAN, APPROVE, few), "D7") == []


def test_d8_measured_or_stated_waits() -> None:
    waiting = dataclasses.replace(LOAD, wait_before=Measure(12, 30, 100))
    f = one(world(PLAN, APPROVE, waiting), "D8")
    assert (f.delta.value, f.delta.text) == (12, "wait 12 min median, 90th percentile 30")
    short = dataclasses.replace(LOAD, wait_before=Measure(3, 4, 100))
    assert found(world(PLAN, APPROVE, short), "D8") == []
    # A step whose accounts state a wait: its activity's duration is the measured wait.
    report = dataclasses.replace(LOAD, stated_wait=15, time=Measure(13.4, 26.6, 200),
                                 wait_before=Measure(39, 51, 200))  # fmt: skip
    assert one(world(PLAN, APPROVE, report), "D8").delta.value == 13.4
    assert found(world(PLAN, APPROVE, report), "D7") == []
    stated = dataclasses.replace(LOAD, stated_wait=15, recorded=None)
    assert one(world(PLAN, APPROVE, stated), "D8").delta.label == STATED


# --- D9 parallel routes and D10 belief gap -------------------------------------------------------


def test_d9_routes_of_at_least_5_percent() -> None:
    f = one(world(variants=[140, 36, 20, 4]), "D9")
    assert (f.keys, f.delta.text) == (("process",), "3 routes: 70%, 18%, 10%, Other 2%")
    assert one(world(variants=[190, 10]), "D9").delta.text == "2 routes: 95%, 5%"  # 5% counts
    assert found(world(variants=[192, 8]), "D9") == []  # the second route is 4%


def test_d10_belief_against_the_measured_value() -> None:
    believed = dataclasses.replace(LOAD, official_min=(10,), time=Measure(16, 25, 100))
    f = one(world(PLAN, APPROVE, believed), "D10")
    assert f.delta.text == f"believed 10 min, measured 16 min ({rules.TIMES}1.6)"
    close = dataclasses.replace(believed, time=Measure(14, 25, 100))  # 1.4 times (A.12 negative)
    assert found(world(PLAN, APPROVE, close), "D10") == []
    lived = dataclasses.replace(LOAD, done_min=10, time=Measure(16, 25, 100))
    assert found(world(PLAN, APPROVE, lived), "D10") == []  # lived accounts aren't belief


# --- D12 different role, D13 design gap, D14 promise missed -------------------------------------


def test_d12_documented_and_done_owner() -> None:
    owner = dataclasses.replace(LOAD, documented_owner="Load control lead", done_owner="Captain")
    assert one(world(PLAN, APPROVE, owner), "D12").delta.text == (
        "Load control lead (documented) vs Captain (done)")  # fmt: skip
    same = dataclasses.replace(owner, done_owner="load control lead")
    assert found(world(PLAN, APPROVE, same), "D12") == []
    assert found(world(), "D12") == []  # nothing said about the owners


def test_d13_numeric_and_confirmed_rule_conflicts() -> None:
    target = IntentOnStep("i1", "target", ("plan",), "lead_time_min", "at_least", 120.0,
                          result="met", documented=90.0, documented_meets=False)  # fmt: skip
    f = one(world(intents=[target]), "D13")
    assert (f.keys, f.delta.text, f.intent_ids) == (
        ("plan",), "target T-120 vs documented T-90", ("i1",))  # fmt: skip
    meets = dataclasses.replace(target, documented=150.0, documented_meets=True)
    assert found(world(intents=[meets]), "D13") == []
    no_metric = IntentOnStep("i2", "policy_rule", ("load",))
    rule = rules.DesignConflict("c1", "i2", ("load",), "The policy screens by risk tier.")
    assert one(world(intents=[no_metric], conflicts=[rule]), "D13").detail["conflict_id"] == "c1"


def test_d14_only_a_metric_not_met() -> None:
    missed = IntentOnStep("i1", "target", ("load",), "wait_min", "at_most", 10.0,
                          result="not_met", actual=13.4, label=MEASURED, met_share=0.21,
                          cases=200)  # fmt: skip
    f = one(world(intents=[missed]), "D14")
    assert (f.delta.text, f.incidence) == ("target 10 vs actual 13; met in 21% of cases", 0.79)
    assert found(world(intents=[dataclasses.replace(missed, result="met")]), "D14") == []
    unknown = IntentOnStep("i2", "promise", ())
    assert found(world(intents=[unknown]), "D14") == []  # intent without a metric


def test_the_rule_set_is_versioned() -> None:
    assert rules.REALITY_RULES_VERSION == "2"
    assert (rules.SHOW_SHARE, rules.REWORK_SHARE, rules.LONGER, rules.WAIT_MIN) == (
        0.05, 0.10, 0.50, 5.0)  # fmt: skip
