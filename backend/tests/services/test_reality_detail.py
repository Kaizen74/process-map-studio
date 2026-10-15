"""The four P13c Reality views (PRD §3.18.3, §5.12.3; P13c): Redline (RV4), Where the time goes
(RV5), Belief vs evidence (RV6) and Typical case (RV7). The phase's checks: a composite is never
below 5 cases and never one case; believed values are medians with "n of N"; waits sit on the
connectors; RQ7 no collisions; and each view's availability message (§3.18.3). Pure: no
database, no AI."""

from __future__ import annotations

import dataclasses
import itertools
import statistics
from typing import Any

import pytest

from app.domain.reality import RealitySnapshot
from app.services import discrepancies as rules
from app.services import reality
from app.services import reality_copy as copy
from app.services import reality_detail as detail
from app.services import reality_shapes as shapes
from app.services.discrepancies import IntentOnStep, Line, Measure
from tests.services.test_discrepancies import APPROVE, LOAD, PLAN, step, world
from tests.services.test_reality import CONFIRMED, RICH, ROUTES, every_figure, inputs, snap

# Five cases on a route that differs from the documented one: minutes to each activity's start,
# then the finish. No two cases agree, so a median is never one case's figure.
TIMINGS = ((0.0, 10.0, 40.0, 50.0), (0.0, 12.0, 44.0, 58.0), (0.0, 8.0, 30.0, 41.0),
           (0.0, 20.0, 60.0, 75.0), (0.0, 15.0, 52.0, 66.0))  # fmt: skip
TYPICAL = reality.RouteIn(2, 30, 0.30, False, ("plan", "plan", "load"), (),
                          activities=("Plan", "Plan", "Load"),
                          positions=("plan", "plan", "load"), timings=TIMINGS)  # fmt: skip
FORTY = tuple((0.0, 9.0 + n, 20.0 + n) for n in range(40))
DOCUMENTED = reality.RouteIn(1, 60, 0.60, True, ("plan", "load"), (),
                             activities=("Plan", "Load"), positions=("plan", "load"),
                             timings=FORTY)  # fmt: skip


def detail_snap(facts: Any = RICH, **fields: Any) -> RealitySnapshot:
    return snap(facts, **({"intents": CONFIRMED} | fields))


# --- RV4 Redline --------------------------------------------------------------------------------


def test_redline_draws_the_documented_steps_once_with_their_markups() -> None:
    s = detail_snap()
    rv4 = s.views.rv4
    documented = [x.key for x in sorted(RICH.steps, key=lambda x: x.order) if x.in_documented]
    assert [x.key for x in rv4.redline.steps] == documented
    assert [k for p in rv4.redline.pages for k in p.step_keys] == documented
    drawn = [r for r in rv4.geometry.shapes if r.role in ("step-documented", "step-ghost")]
    assert [r.key for r in drawn] == documented  # each documented step once, in order
    # One markup per code and type; every markup names its share with a label (§5.12.3).
    pairs = [(m.code, m.type) for m in rv4.redline.markups]
    assert len(pairs) == len(set(pairs))
    assert all(m.share.text and m.share.label for m in rv4.redline.markups)
    kinds = {m.kind for m in rv4.redline.markups}
    assert {"added", "off_system", "no_record", "wait"} <= kinds
    # A waiting capsule sits on a connector, between two steps, never inside one.
    boxes = [(r.x, r.x + r.width) for r in drawn]
    for capsule in (r for r in rv4.geometry.shapes if r.role == "markup-wait"):
        centre = capsule.x + capsule.width / 2
        assert not any(a < centre < b for a, b in boxes)
    assert rv4.availability.state == "ready"


def test_redline_draws_at_most_six_markups_with_every_control_exposure() -> None:
    controls = [step(f"c{n}", n, kind="approval", recorded=False) for n in range(3)]
    added = [step(f"a{n}", 10 + n, in_documented=False, described_in=1) for n in range(9)]
    objectives = [IntentOnStep(f"i{n}", "control_objective", (f"c{n}",)) for n in range(3)]
    facts = world(*controls, *added, intents=objectives,
                  done_lines=[Line("c2", f"a{n}", "sequence") for n in range(9)],
                  documented_lines=[])  # fmt: skip
    s = snap(facts)
    model = s.views.rv4.redline
    drawn = [m for m in model.markups if m.drawn]
    assert len(drawn) == detail.MAX_MARKUPS < len(model.markups)
    control = {c.code for c in s.codes if c.control}
    assert control and control <= {m.code for m in drawn}
    assert set(model.listed) == {m.code for m in model.markups if not m.drawn}
    assert {t.code for t in s.views.rv4.geometry.shapes if t.role == "side-item"} == set(
        model.listed)  # fmt: skip
    assert len({t.code for t in s.views.rv4.geometry.shapes if t.role == "markup-label"}) <= 6


def test_redline_pages_long_processes_by_phase() -> None:
    steps = [step(f"s{n:02}", n) for n in range(15)]
    phases = (reality.PhaseIn("p1", "Plan", 1), reality.PhaseIn("p2", "Load", 2))
    place = {x.key: "p1" if n < 8 else "p2" for n, x in enumerate(steps)}
    s = snap(world(*steps, done_lines=[], documented_lines=[]), phases=phases, step_phase=place)
    pages = s.views.rv4.redline.pages
    assert [p.name for p in pages] == ["Plan", "Load"]
    assert all(len(p.step_keys) <= detail.MAX_STEPS_PER_ROW for p in pages)
    assert [k for p in pages for k in p.step_keys] == [x.key for x in steps]


def test_redline_without_documents_explains_what_it_needs() -> None:
    lived = [dataclasses.replace(x, in_documented=False) for x in RICH.steps]
    s = snap(dataclasses.replace(RICH, steps=tuple(lived)))
    rv4 = s.views.rv4
    assert (rv4.availability.state, rv4.availability.message) == (
        "missing", copy.AVAILABILITY["rv4.no_documents"])  # fmt: skip
    assert rv4.availability.action == "upload_documents"
    assert s.codes and rv4.headline == copy.fill("rv4.none")  # gaps found, but no manual to mark
    assert rv4.redline.steps == [] and rv4.geometry.shapes == []


# --- RV5 Where the time goes --------------------------------------------------------------------

TIMED = world(
    dataclasses.replace(PLAN, documented_min=10.0, done_min=15.0),
    dataclasses.replace(APPROVE, documented_min=5.0, done_min=5.0),
    dataclasses.replace(LOAD, documented_min=20.0, done_min=30.0, stated_wait=12.0),
)  # fmt: skip
PHASED = {"step_phase": {"plan": "p1", "approve": "p1", "load": "p2"}}


def test_where_the_time_goes_uses_one_scale_and_puts_waiting_between_steps() -> None:
    s = snap(TIMED, **PHASED)
    model, geometry = s.views.rv5.time, s.views.rv5.geometry
    assert model.complete and s.views.rv5.availability.state == "ready"
    sized = [r for r in geometry.shapes if r.role in ("manual", "work-designed", "work-extra",
                                                      "wait")]  # fmt: skip
    minutes = {f.id: f.value or 0.0 for c in model.columns
               for f in (c.manual, c.designed, c.extra, c.wait) if f is not None}  # fmt: skip
    assert sized
    ratios = []
    for r in sized:
        column = next(c for c in model.columns if c.column_id == r.key)
        f = {"manual": column.manual, "work-designed": column.designed,
             "work-extra": column.extra, "wait": column.wait}[r.role]  # fmt: skip
        assert f is not None and minutes[f.id] > 0
        ratios.append(r.width / minutes[f.id])
    # The manual's strip and practice's share one scale (widths are rounded to 0.1 px).
    assert max(ratios) - min(ratios) < 0.01 * max(ratios)
    # Waiting is hatched before the column's work, never inside a work box.
    works = [(r.x, r.x + r.width) for r in geometry.shapes if r.role.startswith("work")]
    for wait in (r for r in geometry.shapes if r.role == "wait"):
        assert not any(a < wait.x + 0.1 < b for a, b in works)
    # Totals and the multiplier at the right; the headline names the column adding most time.
    assert model.multiplier is not None and model.multiplier.text.endswith(copy.TIMES)
    load = next(c for c in model.columns if c.name == "Load")
    assert s.views.rv5.headline.startswith("Load adds")
    assert load.wait is not None and load.extra is not None


def test_where_the_time_goes_says_incomplete_without_every_time() -> None:
    s = detail_snap()  # RICH has no documented times
    rv5 = s.views.rv5
    assert not rv5.time.complete and rv5.time.multiplier is None
    assert (rv5.availability.state, rv5.availability.message) == (
        "partial", copy.AVAILABILITY["rv5.no_times"])  # fmt: skip
    assert "No time stated" in {cell for row in rv5.table.rows for cell in row}
    assert rv5.table.rows[-1][-1] == "incomplete"
    totals = [t for t in rv5.geometry.shapes if t.role == "total"]
    assert totals and all(t.lines[0].endswith(", incomplete") for t in totals)


# --- RV6 Belief vs evidence ---------------------------------------------------------------------


def believed(values: tuple[float, ...], measured: float, sources: int = 2) -> Any:
    load = dataclasses.replace(LOAD, official_min=values, official_sources=sources,
                               time=Measure(measured, measured * 1.5, 100))  # fmt: skip
    return world(PLAN, APPROVE, load), {"official_sources": {"load": sources}}


def test_belief_is_the_median_of_stated_values_with_n_of_n() -> None:
    facts, fields = believed((15.0, 20.0, 70.0), 200.0)
    s = snap(facts, **fields, interviews=3)
    [row] = s.views.rv6.belief.rows
    assert row.believed.value == 20.0 and row.believed.label == "stated"  # the median, not one
    assert row.measured.value == 200.0 and row.measured.label == "measured"
    assert row.gap.text == f"{copy.times(10.0)} longer" and row.direction == "longer"
    assert row.prevalence == "stated in 2 of 3 interviews"
    assert s.views.rv6.belief.note == "A visibility gap, not a competence gap."
    assert s.views.rv6.headline == copy.fill("rv6.gap", step="Load", measured="200 min",
                                            believed="20 min")  # fmt: skip
    # No individual answer appears anywhere on the view.
    shown = {f["value"] for f in every_figure(s.views.rv6.model_dump(mode="json"))}
    assert not shown & {15.0, 70.0}
    text = " ".join(line for t in s.views.rv6.geometry.shapes for line in t.lines)
    assert "15 min" not in text and "70 min" not in text


def test_belief_rows_are_belief_gaps_only_and_at_most_six() -> None:
    facts, fields = believed((100.0,), 120.0)  # within the factor: no row
    s = snap(facts, **fields)
    assert s.views.rv6.belief.rows == []
    assert s.views.rv6.headline == copy.fill("rv6.close", factor=copy.times(rules.BELIEF_FACTOR),
                                            steps=copy.count(1, "step"))  # fmt: skip
    many = [step(f"s{n}", n, official_min=(10.0,), official_sources=1,
                 time=Measure(30.0 + n, 40.0, 50)) for n in range(9)]  # fmt: skip
    rows = snap(world(*many, done_lines=[], documented_lines=[])).views.rv6.belief.rows
    assert len(rows) == detail.MAX_BELIEF_ROWS
    assert [r.gap.value for r in rows] == sorted((r.gap.value or 0 for r in rows), reverse=True)


def test_belief_needs_system_records_and_a_stated_time() -> None:
    no_log = snap(dataclasses.replace(RICH, total_cases=0)).views.rv6
    assert (no_log.availability.state, no_log.availability.action) == ("missing", "import_log")
    assert no_log.availability.message == copy.AVAILABILITY["rv6.no_log"]
    nothing = snap(RICH).views.rv6
    assert nothing.availability.message == copy.AVAILABILITY["rv6.no_belief"]
    assert nothing.headline == copy.fill("rv6.none")


def test_belief_needs_at_least_five_measured_cases() -> None:
    load = dataclasses.replace(LOAD, official_min=(10.0,), time=Measure(100.0, 120.0, 4))
    assert snap(world(PLAN, APPROVE, load)).views.rv6.belief.rows == []


# --- RV7 Typical case ---------------------------------------------------------------------------


def test_the_typical_case_is_a_composite_of_the_common_differing_route() -> None:
    read = next(x for x in RICH.steps if x.key == "read")
    steps = tuple(dataclasses.replace(x, recorded=False) if x is read else x for x in RICH.steps)
    facts = dataclasses.replace(
        RICH, steps=steps, done_lines=[*RICH.done_lines, Line("plan", "read", "sequence")]
    )
    s = snap(facts, intents=CONFIRMED, routes=(DOCUMENTED, TYPICAL), system_name="DCS")
    case = s.views.rv7.case
    assert case.cases == 5 and case.label == "A typical case: median timings of 5 cases, not " \
        "one real case."  # fmt: skip
    timed = [e for e in case.events if e.minutes is not None]
    for i, e in enumerate(timed):
        assert e.minutes is not None
        assert e.minutes.value == round(statistics.median(t[i] for t in TIMINGS), 1)
        assert e.minutes.label == "measured"
        # Never one real case's figure: every median here differs from some case's value.
        assert len({t[i] for t in TIMINGS}) > 1 or i == 0
    assert case.actual_finish is not None
    assert case.actual_finish.value == statistics.median(t[-1] for t in TIMINGS)
    assert case.lanes[0].name == "DCS" and case.lanes[0].kind == "system"
    # The steps after Plan without a record sit in their tool's lane (or the off-system lane
    # when no tool is named), with no time of their own.
    off = [e for e in case.events if not e.recorded]
    assert off and all(e.minutes is None for e in off)
    assert {e.lane_id for e in off} == {"tool:spreadsheet", "tool:off-system"}  # Read, Approve
    kinds = {lane.id: lane.kind for lane in case.lanes}
    assert kinds["tool:spreadsheet"] == "tool" and kinds["tool:off-system"] == "off_system"
    assert len(case.lanes) <= detail.MAX_LANES and len(case.events) <= detail.MAX_EVENTS
    assert s.views.rv7.availability.state == "ready"
    tools = next(t for t in case.tiles if t.caption == "touched outside the system")
    assert tools.figure.text == "1 tool"
    paths = [r for r in s.views.rv7.geometry.shapes if r.role == "path"]
    expected = ["solid" if a.recorded and b.recorded else "dotted"
                for a, b in itertools.pairwise(case.events)]  # fmt: skip
    assert [r.style for r in paths] == expected and "dotted" in expected  # dotted off-system


def test_the_typical_case_never_falls_back_below_five_cases() -> None:
    four = dataclasses.replace(TYPICAL, timings=TIMINGS[:4])
    s = snap(RICH, routes=(four,))
    rv7 = s.views.rv7
    assert rv7.case.events == [] and rv7.case.cases == 0 and rv7.geometry.shapes == []
    assert (rv7.availability.state, rv7.availability.message) == (
        "missing", copy.AVAILABILITY["rv7.no_log"])  # fmt: skip
    assert not any(f.startswith("rv7.") for f in s.figures)
    with_documented = snap(RICH, routes=(four, DOCUMENTED)).views.rv7.case
    assert with_documented.cases == 40  # the most common route with at least 5 cases


def test_the_typical_case_against_the_promise() -> None:
    target = reality.IntentIn("t1", "target", "A flight is closed out in 45 minutes.",
                              "process", (), None, "cycle_time_min", "at_most", 45.0, "min",
                              "not_met")  # fmt: skip
    s = snap(RICH, intents=(*CONFIRMED, target), routes=(TYPICAL,))
    case = s.views.rv7.case
    assert case.promise is not None and case.promise.value == 45.0
    late = next(t for t in case.tiles if t.caption == "after the promise")
    assert late.figure.value == round(statistics.median(t[-1] for t in TIMINGS) - 45.0, 1)
    assert s.views.rv7.headline.endswith("after the promise.")
    assert {r.role for r in s.views.rv7.geometry.shapes} >= {"promise", "finish-actual"}


# --- every view: RQ7, tables and figures --------------------------------------------------------


WORLDS = {
    "rich": (RICH, {"intents": CONFIRMED, "routes": ROUTES}),
    "timed": (TIMED, PHASED),
    "case": (RICH, {"intents": CONFIRMED, "routes": (TYPICAL, DOCUMENTED)}),
    "belief": believed((15.0, 20.0, 70.0), 200.0),
    "empty": (world(PLAN, APPROVE, LOAD, total_cases=0), {}),
}


@pytest.mark.parametrize("name", WORLDS)
def test_rq7_no_label_overlaps_another_or_crosses_a_branch(name: str) -> None:
    facts, fields = WORLDS[name]
    s = snap(facts, **fields)
    for view in (s.views.rv4, s.views.rv5, s.views.rv6, s.views.rv7):
        g = view.geometry
        assert shapes.collisions(g.shapes) == [], view.id
        for r in g.shapes:  # everything inside the frame
            assert r.x >= 0 and r.x + r.width <= g.width + 0.01, (view.id, r.role, r.lines)
            assert r.y >= 0 and r.y + r.height <= g.height + 0.01, (view.id, r.role, r.lines)


def test_rq7_the_collision_check_catches_an_overlap() -> None:
    a = shapes.text("x", 10, 10, ["Approve load plan"])
    b = shapes.text("x", 20, 12, ["Load"])
    curve = shapes.arc("arc-loop", 0, 100, 40, 80, style="dashed")
    assert shapes.collisions([a, b]) == [(a, b)]
    assert shapes.collisions([shapes.text("x", 10, 50, ["Plan"]), curve]) != []
    assert shapes.collisions([a, shapes.text("x", 10, 40, ["Load"])]) == []


@pytest.mark.parametrize("name", WORLDS)
def test_each_view_has_a_table_and_ids_from_the_register(name: str) -> None:
    facts, fields = WORLDS[name]
    s = snap(facts, **fields)
    dumped = s.model_dump(mode="json")
    for vid in ("rv4", "rv5", "rv6", "rv7"):
        view = dumped["views"][vid]
        assert view["title"] and view["headline"]
        assert len(view["callouts"]) <= 3
        for f in every_figure(view):
            assert dumped["figures"][f["id"]] == f
        for row in view["table"]["rows"]:
            assert len(row) == len(view["table"]["columns"])


def test_the_detail_views_change_no_earlier_view() -> None:
    """Adding RV4-RV7 leaves Glance, Reality stack and Fix or keep as they were: their parts
    are worked out before the new views and no figure they show is re-registered."""
    s = detail_snap(routes=ROUTES)
    rest = inputs(RICH, intents=CONFIRMED, routes=ROUTES)
    again = reality.build(rest, "1.0.0", frozen=False)
    assert s.views.rv1 == again.views.rv1 and s.views.rv3 == again.views.rv3
    assert s.tiles == again.tiles and s.codes == again.codes


def test_rq7_markup_glyphs_at_one_step_sit_side_by_side() -> None:
    """Two steps added after the same documented step get two "+" glyphs, never one on top of the
    other (found in the browser check, 2026-10-15)."""
    added = [step(f"a{n}", 10 + n, in_documented=False, described_in=1) for n in range(3)]
    facts = world(PLAN, APPROVE, LOAD, *added,
                  done_lines=[Line("plan", f"a{n}", "sequence") for n in range(3)])  # fmt: skip
    s = snap(facts)
    glyphs = [r for r in s.views.rv4.geometry.shapes
              if r.kind == "rect" and r.role.startswith("markup-")]  # fmt: skip
    assert sum(1 for r in glyphs if r.role == "markup-added") >= 2
    assert [(a.code, b.code) for i, a in enumerate(glyphs) for b in glyphs[i + 1 :]
            if shapes.overlaps(a, b)] == []  # fmt: skip
