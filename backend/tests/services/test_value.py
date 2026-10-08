"""The value calculator's rules (PRD §3.14; criterion 90; R9b). Pure, no database."""

from __future__ import annotations

from app.services import value as v
from app.services.value import Figure, StepInputs

MEASURED_TIME = Figure(20.0, v.MEASURED, "log")
STATED_TIME = Figure(30.0, v.ESTIMATED, "SME")
OWN_TIME = Figure(10.0, v.ASSUMED, "Eric")
VOLUME = Figure(120.0, v.MEASURED, "log")
OWN_VOLUME = Figure(60.0, v.ASSUMED, "Eric")


def test_inputs_follow_the_order_of_preference() -> None:
    assert v.first(None, STATED_TIME, OWN_TIME) is STATED_TIME
    assert v.first(MEASURED_TIME, STATED_TIME, OWN_TIME) is MEASURED_TIME
    assert v.first(None, None, None) is None


def test_hours_cost_label_and_scenario_of_a_step() -> None:
    step = StepInputs("s1", measured_time=MEASURED_TIME, measured_volume=VOLUME, hourly_cost=50,
                      disposition="automate_rules")  # fmt: skip
    out = v.step_value(step, v.DEFAULT_REDUCTION)
    assert (out.hours, out.cost, out.label) == (40.0, 2000.0, v.MEASURED)
    assert (out.reduction_pct, out.hours_released, out.cost_released) == (80.0, 32.0, 1600.0)
    mixed = v.step_value(StepInputs("s2", estimated_time=STATED_TIME, override_volume=OWN_VOLUME),
                         {"keep_human": 0.0})  # fmt: skip
    assert (mixed.hours, mixed.label, mixed.cost) == (30.0, v.MIXED, None)
    assert mixed.missing == ["No hourly cost for the lane role."]


def test_a_step_without_both_inputs_has_no_figure_and_says_why() -> None:
    out = v.step_value(StepInputs("s3", estimated_time=STATED_TIME, role_name="Ramp"), {})
    assert (out.hours, out.cost, out.label, out.hours_released) == (None, None, None, None)
    assert out.missing == ["No volume per month: none measured, no override."]


def test_totals_count_what_is_missing_and_what_has_no_cost() -> None:
    a = v.step_value(StepInputs("a", measured_time=MEASURED_TIME, measured_volume=VOLUME,
                                hourly_cost=10), {})  # fmt: skip
    b = v.step_value(StepInputs("b", estimated_time=STATED_TIME, measured_volume=VOLUME), {})
    c = v.step_value(StepInputs("c"), {})
    totals = v.totals([a, b, c], {"a": "p1", "b": "p1", "c": "p2"})
    p1 = totals["p1"]
    assert (p1.hours, p1.cost, p1.counted, p1.costed, p1.label) == (100.0, 400.0, 2, 1, v.MIXED)
    assert (totals["p2"].counted, totals["p2"].missing, totals["p2"].label) == (0, 1, None)
    rows = v.scenarios([a, b, c])
    assert rows["keep_human"] == {"steps": 3, "hours": 100.0, "hours_released": 0.0,
                                  "cost_released": 0.0}  # fmt: skip
    assert list(rows) == list(v.DEFAULT_REDUCTION)
