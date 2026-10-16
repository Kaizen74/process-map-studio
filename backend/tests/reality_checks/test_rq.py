"""The automated Reality checks RQ1-RQ10 (PRD §5.12.8; part of run_checks.sh from P13d) on
fixture A.12 published with the Reality views on: the snapshot as the Reality screen reads it,
Leadership's shared figures and the Reality pack in both layouts. RQ3's token scan of
`components/reality/` and RQ7's and RQ8's browser parts run with the frontend checks
(designSystem.test.ts, the smoke path); this suite covers the rest, and the pack's own CSS for
RQ3. Claude is mocked throughout."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.domain.reality import Shape
from app.services import export_reality, reality_detail, wording
from app.services.reality_shapes import collisions
from tests.unit.test_discrepancies_a12 import a12
from tests.unit.test_intent_api import build
from tests.unit.test_reality_api import publish, snapshot, switch

ARC_OR_GLYPH = {  # RQ2: each discrepancy kind and the component that draws it on the Redline
    "skipped": "arc-skipped", "bypass": "arc-bypass", "reorder": "arc-reorder",
    "loop": "arc-loop", "wait": "markup-wait", "added": "markup-added",
    "off_system": "markup-off-system", "no_record": "markup-no-record", "owner": "markup-owner",
    "longer": "markup-longer",
}  # fmt: skip
SHAPE_VIEWS = ("rv4", "rv5", "rv6", "rv7")


@dataclass
class World:
    client: TestClient
    eid: str
    vid: str
    snap: dict[str, Any]
    packs: dict[str, str]  # layout → HTML
    leadership: dict[str, Any]


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> Iterator[World]:
    folder = tmp_path_factory.mktemp("rq")
    config = load_config({"PMS_ENV_FILE": str(folder / ".env"), "MOCK_CLAUDE": "1",
                          "DATA_DIR": str(folder / "data")})  # fmt: skip
    for engagement in build(config):
        reality = a12(engagement, with_log=True)
        client, vid = engagement.client, reality.version_id
        switch(client, True)
        publish(client, vid)
        packs = {}
        for layout in ("a3", "slide"):
            response = client.get(f"/api/versions/{vid}/reality/export", params={"layout": layout})
            assert response.status_code == 200, response.text
            packs[layout] = response.text
        leadership = client.get(f"/api/versions/{vid}/leadership").json()["reality"]
        yield World(client, engagement.eid, vid, snapshot(client, vid), packs, leadership)


def code_impacts(snap: dict[str, Any]) -> dict[str, str]:
    return {c["code"]: c["impact_class"] for c in snap["codes"]}


def test_rq1_shared_axis(world: World) -> None:
    """Documented, believed and observed marks of a column share one x range."""
    g = world.snap["views"]["rv2"]["geometry"]
    columns = {c["id"]: c for c in g["columns"]}
    assert g["marks"]
    for m in g["marks"]:
        col = columns[m["column_id"]]
        assert col["x"] <= m["x"] and m["x"] + m["width"] <= col["x"] + col["width"] + 0.01, m


def test_rq2_symbol_fidelity(world: World) -> None:
    """Each discrepancy is drawn with its D-type component."""
    rv4 = world.snap["views"]["rv4"]
    shapes = rv4["geometry"]["shapes"]
    for m in rv4["redline"]["markups"]:
        assert reality_detail.MARKUP_KINDS[m["type"]][0] == m["kind"], m
        if m["drawn"]:
            roles = {s["role"] for s in shapes if s["code"] == m["code"]}
            assert ARC_OR_GLYPH[m["kind"]] in roles, (m["code"], m["kind"], roles)
    branches = [m for m in world.snap["views"]["rv2"]["geometry"]["marks"] if m["code"]]
    assert branches and all(m["kind"] == "branch" for m in branches)


def test_rq3_the_pack_uses_impact_colours_only_through_the_reality_styles(world: World) -> None:
    """The pack's own layout styles never use an impact colour: impact appears only through the
    Reality components' classes (whose token scan runs in designSystem.test.ts)."""
    css = (Path(__file__).parents[2] / "app" / "services" / "export_reality.css").read_text()
    assert not re.search(r"--(impact-|designed-work|baseline-)", css)
    for html in world.packs.values():
        styled = re.findall(r'style="([^"]*)"', html)
        assert all("impact" not in s for s in styled)


def test_rq4_identity(world: World) -> None:
    """Every X code has one colour (impact class), glyph and title across all views, the panel's
    source (the snapshot's codes) and the pack."""
    snap = world.snap
    impact = code_impacts(snap)
    titles = {c["code"]: c["title"] for c in snap["codes"]}
    glyphs = {c["impact_class"]: c["glyph"] for c in snap["codes"]}
    assert len(glyphs) == len(set(glyphs.values()))  # one glyph per impact class
    views = snap["views"]
    for m in views["rv2"]["geometry"]["marks"]:
        if m["code"]:
            assert m["impact_class"] == impact[m["code"]], m
    for vid in SHAPE_VIEWS:
        for s in views[vid]["geometry"]["shapes"]:
            if s["code"] and s["impact_class"]:
                assert s["impact_class"] == impact[s["code"]], (vid, s)
    for m in views["rv4"]["redline"]["markups"]:
        assert m["impact_class"] == impact[m["code"]]
    for vid, view in views.items():
        for c in view["callouts"]:
            if c["code"]:
                assert c["impact_class"] == impact[c["code"]], (vid, c)
    for html in world.packs.values():
        tags = re.findall(r'class="x-tag x-tag--(\w+)">(X\d+)<', html)
        assert tags and all(impact[code] == cls for cls, code in tags)
        for code, title in titles.items():
            assert re.search(rf">{code}</span></td><td>{re.escape(title)}<", html), code


def test_rq5_every_drawn_discrepancy_has_a_labelled_delta(world: World) -> None:
    labels = {"measured", "stated", "documented", "target", "mixed", "estimated"}
    for c in world.snap["codes"]:
        assert c["delta"]["text"] and c["delta"]["label"] in labels, c["code"]
    for m in world.snap["views"]["rv4"]["redline"]["markups"]:
        assert m["share"]["text"] and m["share"]["label"] in labels


def test_rq6_density_and_control_exposures_present(world: World) -> None:
    v = world.snap["views"]
    assert len([c for c in world.snap["columns"] if c["kind"] != "process"]) <= 7
    assert len(world.snap["tiles"]) <= 5
    assert len(v["rv1"]["glance"]["routes"]) <= 7
    assert len(v["rv2"]["stack"]["highlighted"]) <= 5
    assert sum(1 for m in v["rv4"]["redline"]["markups"] if m["drawn"]) <= 6
    assert len(v["rv6"]["belief"]["rows"]) <= 6
    assert len(v["rv7"]["case"]["lanes"]) <= 6 and len(v["rv7"]["case"]["events"]) <= 15
    assert all(len(view["callouts"]) <= 3 for view in v.values())
    controls = {c["code"] for c in world.snap["codes"] if c["control"]}
    assert controls
    stack = v["rv2"]["stack"]
    assert controls <= set(stack["highlighted"]) | set(stack["listed"])
    assert controls <= {m["code"] for m in v["rv4"]["redline"]["markups"] if m["drawn"]}
    assert controls <= {p["code"] for p in v["rv3"]["fix"]["circles"]}
    for html in world.packs.values():  # never hidden in the pack either
        interpretation = html[html.index('data-section="interpretation"') :]
        for code in controls:
            assert f">{code}</span>" in interpretation


def test_rq7_no_label_collides(world: World) -> None:
    """In the geometry (any size scales it evenly: 1600 x 1000, 1080 wide, A3 and 16:9 alike),
    and no drawing printed smaller than its text allows; the browser check measures the pages."""
    for vid in SHAPE_VIEWS:
        g = world.snap["views"][vid]["geometry"]
        assert collisions([Shape.model_validate(s) for s in g["shapes"]]) == [], vid
    for layout, html in world.packs.items():  # every drawing the pack prints keeps 11 px text
        for w, h in re.findall(r'class="reality-canvas" viewBox="0 0 ([\d.]+) ([\d.]+)"', html):
            assert export_reality.legible(float(w), float(h), layout), (layout, w, h)
    marks = world.snap["views"]["rv2"]["geometry"]["marks"]
    for i, a in enumerate(marks):
        for b in marks[i + 1 :]:
            if a["column_id"] == b["column_id"] and a["band_id"] == b["band_id"]:
                apart = a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
                assert apart, (a["lines"], b["lines"])


def test_rq8_every_impact_reads_without_colour(world: World) -> None:
    """Each impact class carries its own glyph and word wherever its colour appears."""
    impacts = world.snap["legend"]["impacts"]
    assert len({i["glyph"] for i in impacts}) == len({i["word"] for i in impacts}) == 4
    for c in world.snap["codes"]:
        assert c["glyph"] and c["impact_word"]
    for html in world.packs.values():
        for i in impacts:
            assert f"impact-glyph--{i['impact_class']}" in html and f"{i['word']}</span>" in html
        # every coloured code tag carries its code in words
        assert re.findall(r'class="x-tag x-tag--\w+"></span>', html) == []


def test_rq9_one_number_everywhere(world: World) -> None:
    """Each figure ID has one value on every view, Leadership and the pack (G17)."""
    figures = world.snap["figures"]

    def walk(value: Any) -> Iterator[dict[str, Any]]:
        if isinstance(value, dict):
            if {"id", "value", "unit", "text", "label"} <= set(value):
                yield value
            for v in value.values():
                yield from walk(v)
        elif isinstance(value, list):
            for v in value:
                yield from walk(v)

    seen = list(walk(world.snap["views"])) + list(walk(world.snap["codes"]))
    assert seen
    for f in seen:
        assert figures[f["id"]] == f
    for t in world.leadership["tiles"]:
        assert figures[t["figure"]["id"]] == t["figure"]
    for html in world.packs.values():
        printed = re.findall(r'data-figure="([^"]+)"[^>]*>([^<]*)<', html)
        assert printed
        for fid, text in printed:
            assert figures[fid]["text"] == text.replace("&amp;", "&"), fid


def test_rq10_tone_and_names(world: World) -> None:
    """No banned word, no name from the redaction list and no person, on any view or page."""
    terms = [t["term"] for t in
             world.client.get(f"/api/engagements/{world.eid}/redaction-terms").json()]  # fmt: skip
    assert terms
    texts = [str(world.snap)] + [re.sub(r"<style>.*?</style>", "", h, flags=re.S)
                                 for h in world.packs.values()]  # fmt: skip
    for text in texts:
        words = re.sub(r"<[^>]+>", " ", text)
        assert wording.banned_words(words) == []
        for term in terms:
            assert term.casefold() not in words.casefold(), term
