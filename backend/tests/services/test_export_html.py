"""The single-file HTML map (PRD §7.3, §3.10; constraints 9-11, 20): drawn from the backend layout,
styled with the shared tokens and embedded fonts, no outside requests, no script, no images, no
quotes; three separate sections; every step on the map links to its details."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.services import export_html
from app.services import exports as md
from tests.services.test_exports import ROOT, SAMPLE, data, sample_graph

TOKENS = json.loads((ROOT / "shared" / "design_tokens.json").read_text(encoding="utf-8"))
FONT_DIR = ROOT / "frontend" / "public" / "fonts"
FONTS = {path.name: path.read_bytes() for path in FONT_DIR.glob("*.woff2")}
CSS = Path(export_html.__file__).with_name("export_html.css")


def render(**changes: object) -> str:
    return export_html.render_map_html(data(**changes), TOKENS, FONTS)


def test_one_self_contained_file_with_no_outside_requests() -> None:
    html = render()
    assert html.startswith('<!doctype html>\n<html lang="en">')
    csp = "default-src 'none'; style-src 'unsafe-inline'; font-src data:"
    assert f'<meta http-equiv="Content-Security-Policy" content="{csp}">' in html
    assert not re.search(r"https?://", html)
    assert "<script" not in html and "<img" not in html and "<link" not in html
    assert all(
        url.startswith("url(data:font/woff2;base64,")
        for url in re.findall(r"url\([^)]{0,40}", html)
    )
    assert html.count("@font-face") == 8  # Sans and Mono, 400 and 500, Latin and Latin Extended


def test_styles_come_only_from_the_shared_tokens() -> None:
    html = render()
    for name, value in TOKENS["color"].items():
        assert f"--{name}: {value};" in html
    assert f"--space-16: {TOKENS['space']['16']};" in html
    css = CSS.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "a raw colour in the export stylesheet"
    assert not re.search(r"rgba?\(", css)


def test_the_map_is_drawn_from_the_layout_and_links_to_each_step() -> None:
    html = render()
    anchors = re.findall(r'<a class="node [a-z_]+" href="#step-([^"]+)"', html)
    assert len(anchors) == 12  # 10 steps (v1.10 A.5) plus start and end
    targets = set(re.findall(r'<article class="card step" id="step-([^"]+)"', html))
    steps = [e.id for e in md.steps(sample_graph())]
    assert targets == set(steps)
    assert set(steps) <= set(anchors)
    assert 'aria-label="Activity, Draft load plan, Load controller, Corroborated"' in html
    assert 'aria-label="Load controller lane, 6 steps"' in html  # v1.10 A.5
    # Three steps without time (v1.10 A.5), as on the map.
    assert html.count('class="lens danger"') == 3
    assert '<span class="chip"' in html and 'class="arrow right"' in html


def test_three_separate_sections_with_recommendations_only_in_the_third() -> None:
    html = render()
    ids = re.findall(r'<section aria-labelledby="([a-z]+)">', html)
    assert ids == ["facts", "interpretation", "recommendation"]
    before = html.split('<section aria-labelledby="recommendation">')[0]
    assert "<dt>Component</dt>" not in before and "Widebody plans rely" not in before
    after = html.split('<section aria-labelledby="recommendation">')[1]
    assert after.count("<dt>Component</dt>") == 3


def test_no_quotes_and_rejected_steps_left_out() -> None:
    passages = [
        s["text"]
        for page in json.loads(SAMPLE.read_text(encoding="utf-8"))["segments"].values()
        for s in page["segments"]
        if len(s["text"]) > 40
    ]
    graph = sample_graph()
    issue = next(e for e in graph.elements if e.label == "Issue load sheet")
    issue.review_status = "rejected"
    html = export_html.render_map_html(data(graph), TOKENS, FONTS)
    assert "Issue load sheet" not in html
    assert not [p for p in passages if p in html]


def test_text_is_escaped() -> None:
    graph = sample_graph()
    graph.elements[1].label = 'Plan <b>"now"</b> & go'
    html = export_html.render_map_html(data(graph), TOKENS, FONTS)
    assert '<b>"now"</b>' not in html
    assert "Plan &lt;b&gt;&quot;now&quot;&lt;/b&gt; &amp; go" in html


def test_the_quality_card_heads_the_page() -> None:
    html = render()
    assert html.index("Quality card") < html.index('aria-labelledby="facts"')
    assert '<td class="warning">Warning</td>' in html
    assert "Quality card: not worked out yet." in render(quality_card=None)
