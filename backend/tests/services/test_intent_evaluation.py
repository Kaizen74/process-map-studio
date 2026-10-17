"""Intent evaluation (PRD §3.16 "Evaluation"; P13a-3a): measured → stated → documented, and
"unknown" shown honestly. Pure: no database, no AI."""

from __future__ import annotations

from app.services import intent as rules
from app.services.intent import Target, Values

WAIT = Target("wait_min", "at_most", 10.0)
LEAD = Target("lead_time_min", "at_least", 120.0)


def test_measured_cases_come_first_with_the_share_meeting_the_target() -> None:
    e = rules.evaluate(WAIT, Values(measured=13.4, measured_cases=200, within=42, stated=15.0,
                                    documented=10.0))  # fmt: skip
    assert (e.result, e.actual, e.label, e.met_share, e.cases) == (
        "not_met", 13.4, "measured", 0.21, 200)  # fmt: skip
    assert (e.documented, e.documented_meets) == (10.0, True)


def test_fewer_than_5_cases_fall_back_to_the_stated_value() -> None:
    e = rules.evaluate(WAIT, Values(measured=8.0, measured_cases=4, stated=15.0))
    assert (e.result, e.actual, e.label, e.met_share) == ("not_met", 15.0, "stated", None)


def test_lead_time_from_the_lived_and_documented_offsets() -> None:
    e = rules.evaluate(LEAD, Values(stated=120.0, documented=90.0))
    assert (e.result, e.label, e.documented_meets) == ("met", "stated", False)
    only_documented = rules.evaluate(LEAD, Values(documented=90.0))
    assert (only_documented.result, only_documented.label) == ("not_met", "documented")


def test_nothing_known_is_unknown_never_met() -> None:
    assert rules.evaluate(WAIT, Values()).result == "unknown"
    equals = Target("step_time_min", "equals", 5.0)
    assert rules.evaluate(equals, Values(stated=5.0)).result == "met"


def test_a_control_objective_is_not_met_where_its_step_fails() -> None:
    e = rules.evaluate_without_metric("control_objective", [("D11", 1.0, 200), ("D2", None, None)])
    assert (e.result, e.met_share, e.cases, e.label) == ("not_met", 0.0, 200, "measured")
    stated = rules.evaluate_without_metric("control_objective", [("D1", None, None)])
    assert (stated.result, stated.label) == ("not_met", "stated")
    assert rules.evaluate_without_metric("control_objective", [("D8", 0.3, 10)]).result == (
        "unknown")  # fmt: skip
    assert rules.evaluate_without_metric("promise", [("D11", 1.0, 200)]).result == "unknown"
