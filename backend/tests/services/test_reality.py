"""The Reality snapshot's rules (PRD §3.18, §5.12; P13b): determinism, figures from one register,
copy from templates only, and the automated checks RQ1, RQ2, RQ4, RQ5 and RQ6 for Glance, Reality
stack and Fix or keep. Pure: no database, no AI."""

from __future__ import annotations

import dataclasses
import itertools
import re
from collections.abc import Iterator
from typing import Any

import pytest

from app.domain.reality import Figure, RealitySnapshot
from app.services import discrepancies as rules
from app.services import reality, wording
from app.services import reality_copy as copy
from app.services import verdicts as verdict_rules
from app.services.discrepancies import Facts, IntentOnStep, Measure
from tests.services.test_discrepancies import APPROVE, LINES, LOAD, PLAN, step, world

PHASES = (reality.PhaseIn("p1", "Plan", 1), reality.PhaseIn("p2", "Load", 2))
STEP_PHASE = {"plan": "p1", "approve": "p1", "load": "p2", "walk": "p2", "read": "p2"}
LABELS = {"measured", "stated", "documented", "target", "mixed", "estimated"}


def inputs(facts: Facts, **fields: Any) -> reality.Inputs:
    """The inputs the action would gather, with codes given in the engine's order."""
    found = [f for f in rules.detect(facts) if f.shown]
    groups = [g for g in verdict_rules.group(found, facts) if g.kind != "process"]
    impacts = {g.location_key: verdict_rules.impact(g, facts) for g in groups}
    items = {}
    for n, g in enumerate(verdict_rules.code_order(groups, facts, impacts), start=1):
        items[g.location_key] = reality.ItemIn(f"item-{n}", f"X{n}", " → ".join(g.keys), None, "")
    base: dict[str, Any] = {
        "version_id": "v1", "process_name": "Load control", "draft": True,
        "data_label": "Draft: figures may change", "facts": facts, "phases": PHASES,
        "step_phase": STEP_PHASE, "routes": (), "routes_other": 0, "intents": (),
        "items": items, "documents": 1, "interviews": 2, "official_sources": {},
        "activity_after": {}, "volume": None, "cycle_min": None,
    }  # fmt: skip
    return reality.Inputs(**(base | fields))


def snap(facts: Facts, **fields: Any) -> RealitySnapshot:
    return reality.build(inputs(facts, **fields), "1.0.0", frozen=False)


OBJECTIVE = IntentOnStep("i1", "control_objective", ("approve",))
UNRECORDED = dataclasses.replace(APPROVE, recorded=False, cases=0)
WAITING = dataclasses.replace(LOAD, usual_route=True, per_month=100,
                              wait_before=Measure(12, 20, 100))  # fmt: skip
WALK = step("walk", 3, in_documented=False, described_in=1, done_min=10.0)
READ = step("read", 4, in_documented=False, described_in=1, tools=("spreadsheet",))
RICH = world(PLAN, UNRECORDED, WAITING, WALK, READ, intents=[OBJECTIVE],
             done_lines=[*LINES, rules.Line("load", "walk", "sequence"),
                         rules.Line("walk", "read", "sequence")])  # fmt: skip
CONFIRMED = (reality.IntentIn("i1", "control_objective", "Every plan is approved.", "step",
                              ("approve",), None, None, None, None, None, "not_met"),)  # fmt: skip
ROUTES = (
    reality.RouteIn(1, 70, 0.70, True, ("plan", "load"), ()),
    reality.RouteIn(2, 20, 0.20, False, ("plan", "plan", "load"), ()),
    reality.RouteIn(3, 8, 0.08, False, ("plan", "load"), ("Manual fix",)),
)


def every_figure(value: Any) -> Iterator[dict[str, Any]]:
    """Every figure object anywhere in a dumped snapshot."""
    if isinstance(value, dict):
        if {"id", "value", "unit", "text", "label"} <= set(value):
            yield value
        for v in value.values():
            yield from every_figure(v)
    elif isinstance(value, list):
        for v in value:
            yield from every_figure(v)


def template_patterns() -> list[re.Pattern[str]]:
    return [re.compile("^" + re.sub(r"\\\{\w+\\\}", ".+", re.escape(t)) + "$")
            for t in copy.TEMPLATES.values()]  # fmt: skip


def from_templates(text: str) -> bool:
    patterns = template_patterns()
    sentences = re.findall(r"[^.]+\.(?:\s|$)|[^.]+$", text)
    return all(any(p.match(s.strip()) for p in patterns) for s in sentences if s.strip())


# --- determinism and one register (G17) ---------------------------------------------------------


def test_the_same_inputs_give_a_byte_identical_snapshot() -> None:
    one, two = snap(RICH, intents=CONFIRMED), snap(RICH, intents=CONFIRMED)
    assert reality.serialise(one) == reality.serialise(two)
    assert one.inputs_hash == reality.inputs_hash(inputs(RICH, intents=CONFIRMED))
    other = snap(dataclasses.replace(RICH, total_cases=120), intents=CONFIRMED)
    assert other.inputs_hash != one.inputs_hash
    assert (one.rules_version, one.copy_version, one.layout_version) == ("1", "1", "1")


def test_every_figure_has_one_value_everywhere() -> None:
    """RQ9 within a snapshot: a figure drawn anywhere is the register's figure with that ID."""
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    dumped = s.model_dump(mode="json")
    register = dumped["figures"]
    seen = list(every_figure(dumped["views"])) + list(every_figure(dumped["tiles"])) + list(
        every_figure(dumped["codes"]))  # fmt: skip
    assert seen
    for f in seen:
        assert register[f["id"]] == f
        assert f["label"] in LABELS
    for figure in register.values():
        Figure.model_validate(figure)


# --- copy from templates only (constraint 26) ---------------------------------------------------


@pytest.mark.parametrize("fields", [
    {"intents": CONFIRMED, "routes": ROUTES, "volume": 100.0},
    {"intents": CONFIRMED},
    {},
])  # fmt: skip
def test_headlines_and_callouts_come_from_templates(fields: dict[str, Any]) -> None:
    s = snap(RICH, **fields)
    for view in (s.views.rv1, s.views.rv2, s.views.rv3):
        assert view.headline and from_templates(view.headline), view.headline
        assert copy.words(view.headline) <= copy.MAX_HEADLINE_WORDS
        assert len(view.callouts) <= 3
        for c in view.callouts:
            assert 1 <= len(c.lines) <= 2
            assert all(from_templates(line) or line in (cv.verdict.reason for cv in s.codes
                                                        if cv.verdict)
                       for line in c.lines), c.lines  # fmt: skip
    assert s.views.rv1.title == "How different is real Load control from the manual?"


def test_the_catalogue_is_neutral_and_names_no_one() -> None:
    text = " ".join(copy.every_template())
    assert wording.banned_words(text) == []
    for word in ("fail", "blame", "fault", "staff fail", "conformance", "fitness", "variant"):
        assert word not in text.casefold()


# --- tiles (§3.18.5) ----------------------------------------------------------------------------


def test_tiles_with_system_records() -> None:
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    tiles = {t.figure.id: (t.figure.text, t.figure.label, t.caption) for t in s.tiles}
    assert tiles["rv1.documented_share"] == ("70%", "measured", "of cases follow the manual")
    assert tiles["rv1.control_share"][0] == "100%"
    assert s.views.rv1.headline.startswith("Only 70% of cases follow the manual.")
    assert "leave no record of" in s.views.rv1.headline


def test_tiles_without_system_records_use_step_counts() -> None:
    no_log = world(PLAN, APPROVE, LOAD, WALK, total_cases=0,
                   done_lines=[*LINES, rules.Line("load", "walk", "sequence")])  # fmt: skip
    s = snap(no_log)
    [tile] = [t for t in s.tiles if t.figure.id == "rv1.practised"]
    assert (tile.figure.text, tile.figure.label, tile.caption) == (
        "3 of 3", "stated", "steps practised as documented")  # fmt: skip
    assert s.views.rv1.glance.basis == "steps"
    assert s.views.rv1.availability.action == "import_log"
    assert s.views.rv1.headline == "1 step happens only in practice and 0 steps only in the manual."


def test_a_tile_whose_inputs_are_missing_is_left_out() -> None:
    # Only one documented activity states a time: the designed total is incomplete.
    timed = dataclasses.replace(PLAN, documented_min=10.0)
    s = snap(world(timed, APPROVE, LOAD), cycle_min=60.0)
    assert "rv1.multiplier" not in {t.figure.id for t in s.tiles}
    complete = [dataclasses.replace(x, documented_min=10.0) for x in (PLAN, LOAD)]
    s = snap(world(complete[0], APPROVE, complete[1]), cycle_min=60.0)
    [x] = [t for t in s.tiles if t.figure.id == "rv1.multiplier"]
    assert (x.figure.text, x.figure.label) == (f"3.0{copy.TIMES}", "mixed")


# --- RQ1, RQ2, RQ4, RQ5, RQ6 ------------------------------------------------------------------


def test_rq1_every_mark_sits_in_its_column() -> None:
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    g = s.views.rv2.geometry
    boxes = {b.id: b for b in g.columns}
    for m in g.marks:
        b = boxes[m.column_id]
        assert b.x <= m.x and m.x + m.width <= b.x + b.width + 0.1, m
    for col in boxes:
        ranges = {(m.x, m.width) for m in g.marks if m.column_id == col
                  and m.band_id in ("documented", "belief", "done")}  # fmt: skip
        assert len(ranges) <= 1  # documented, believed and observed share one x range
    bands = sorted(g.bands, key=lambda b: b.y)
    assert all(a.y + a.height <= b.y for a, b in itertools.pairwise(bands))


def test_rq2_and_rq4_a_code_is_the_same_in_every_view() -> None:
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    by_code = {c.code: c for c in s.codes}
    for band in s.views.rv2.stack.bands:
        for cell in band.cells:
            for i in cell.items:
                if i.kind == "branch":
                    c = by_code[i.code or ""]
                    assert (i.impact_class, i.figure, i.label) == (c.impact_class, c.delta, c.title)
                    assert band.id == ("documented" if c.location.kind == "design" else "done")
    for route in s.views.rv1.glance.routes:
        assert set(route.codes) <= set(by_code)
    assert {p.code for p in s.views.rv3.fix.circles} <= set(by_code)
    for c in s.codes:
        word, glyph = copy.IMPACT_WORDS[c.impact_class]
        assert (c.impact_word, c.glyph) == (word, glyph)
        rows = [r for r in s.views.rv3.table.rows if r[0] == c.code]
        assert rows and rows[0][1] == c.title
        assert rows[0][5] == (c.hours.text if c.hours else "Needs system records")


def test_rq5_every_drawn_code_has_a_labelled_delta() -> None:
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    assert s.codes
    for c in s.codes:
        assert c.delta.text and c.delta.label in LABELS
        assert c.hours is not None and c.hours.label == "measured"


def test_rq6_density_and_control_exposures_never_hidden() -> None:
    controls = [step(f"c{n}", n, kind="approval", recorded=False) for n in range(4)]
    added = [step(f"a{n}", 10 + n, in_documented=False, described_in=1) for n in range(9)]
    facts = world(*controls, *added, done_lines=[], documented_lines=[])
    many = tuple(reality.PhaseIn(f"p{n}", f"Phase {n}", n) for n in range(10))
    place = {s.key: f"p{n % 10}" for n, s in enumerate(facts.steps)}
    s = snap(facts, phases=many, step_phase=place)
    assert len(s.columns) <= 8 and s.columns[-1].id == "process"
    assert s.columns_note.endswith("not shown, none with a control exposure")
    stack = s.views.rv2.stack
    assert len(stack.highlighted) <= 5
    assert sum(1 for c in s.codes if c.code in stack.highlighted and c.control) <= 2
    control = {c.code for c in s.codes if c.control}
    assert control and control <= set(stack.highlighted) | set(stack.listed)
    assert control <= {p.code for p in s.views.rv3.fix.circles}
    kept = {c.id for c in s.columns}
    assert all(c.column_id in kept for c in s.codes if c.control)
    assert len(s.tiles) <= 5 and len(s.views.rv1.glance.routes) <= 7


# --- what each view shows without its inputs (§3.18.3) ------------------------------------------


def test_without_intent_every_gap_sits_in_ask() -> None:
    s = snap(dataclasses.replace(RICH, intents=[]))
    assert {p.zone for p in s.views.rv3.fix.circles} == {"ask"}
    assert s.views.rv3.availability.action == "add_intent"
    assert s.views.rv3.headline.endswith("in Ask until intent is confirmed.")
    promise = next(b for b in s.views.rv2.stack.bands if b.id == "promise")
    assert (promise.state, promise.message) == ("missing", copy.AVAILABILITY["rv2.no_intent"])


def test_without_documents_the_manual_band_says_so() -> None:
    lived = [dataclasses.replace(x, in_documented=False) for x in (PLAN, LOAD)]
    s = snap(world(*lived, total_cases=0), documents=0)
    documented = next(b for b in s.views.rv2.stack.bands if b.id == "documented")
    assert (documented.state, documented.message) == ("missing", "No documents uploaded.")
    assert s.views.rv1.availability.action == "upload_documents"
    assert s.views.rv1.headline == (
        "No manual to compare with yet: 2 steps come from interviews only.")  # fmt: skip


def test_fix_or_keep_places_codes_by_verdict_and_eric_wins() -> None:
    s = snap(RICH, intents=CONFIRMED)
    x = next(c for c in s.codes if "D11" in c.types)
    assert x.verdict and (x.verdict.shown, x.verdict.status) == ("correct", "suggested")
    assert next(p.zone for p in s.views.rv3.fix.circles if p.code == x.code) == "correct"
    decided = dict(inputs(RICH).items)
    key = next(k for k, i in decided.items() if i.code == x.code)
    decided[key] = dataclasses.replace(decided[key], verdict_decided="codify", verdict_note="Keep.")
    s = snap(RICH, intents=CONFIRMED, items=decided)
    y = next(c for c in s.codes if c.code == x.code)
    assert y.verdict and (y.verdict.shown, y.verdict.status, y.verdict.note) == (
        "codify", "confirmed", "Keep.")  # fmt: skip
    assert next(p.zone for p in s.views.rv3.fix.circles if p.code == x.code) == "codify"
    assert s.views.rv3.fix.note == "Verdicts are recommendations; the process owner decides."


def test_glance_routes_from_the_log() -> None:
    rework = dataclasses.replace(PLAN, recorded=True, cases=100, rework_cases=20)
    facts = world(rework, APPROVE, LOAD, hidden=[rules.HiddenWork("Manual fix", 8, 10.0, 5.0)],
                  variants=[70, 20, 8])  # fmt: skip
    s = snap(facts, routes=ROUTES, routes_other=2)
    routes = [(r.name, r.share.text, r.codes) for r in s.views.rv1.glance.routes]
    assert routes[0][:2] == ("As documented", "70%")
    names = [r[0] for r in routes]
    assert "Repeats Plan" in names and "Adds Manual fix" in names
    other = next(r for r in s.views.rv1.glance.routes if r.id == "other")
    assert other.other_count == 2 and other.share.text == "2%"
    g = s.views.rv1.geometry
    assert [r.route_id for r in g.ribbons] == [r.id for r in s.views.rv1.glance.routes]
    assert g.ribbons[0].width == pytest.approx(round(26 * 0.70, 1))
    assert all(r.width >= 1.5 for r in g.ribbons)


def test_table_equivalents_carry_the_same_figures() -> None:
    s = snap(RICH, intents=CONFIRMED, routes=ROUTES, volume=100.0)
    rv1 = s.views.rv1
    assert [r[1] for r in rv1.table.rows] == [r.share.text for r in rv1.glance.routes]
    text = " ".join(" ".join(r) for r in s.views.rv2.table.rows)
    for band in s.views.rv2.stack.bands:
        for cell in band.cells:
            for i in cell.items:
                if i.figure is not None:
                    assert i.figure.text in text
