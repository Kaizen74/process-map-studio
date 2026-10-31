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
        if name.startswith(("impact-", "designed-work", "baseline-")):
            # PRD §5.2: the Reality tokens are for the Reality views and pack only (P13b).
            assert f"--{name}:" not in html
        else:
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


def test_both_views_are_drawn_with_not_described_lines_dashed() -> None:
    """§3.12.11: both views are published together (K3, 2026-10-06)."""
    from tests.services.test_exports import sensemaking_data

    html = export_html.render_map_html(sensemaking_data(), TOKENS, FONTS)
    done = html.index("<h3>Map as done: the work as actually performed</h3>")
    documented = html.index("<h3>Map as documented: the documents&#x27; version</h3>")
    assert done < documented < html.index("<h3>Steps</h3>")
    assert html.count('role="group" aria-label="Swimlane map"') == 2
    as_done = html[done:documented]
    assert 'aria-label="Activity, Read report at aircraft' in as_done
    assert 'aria-label="Approval, Approve load plan' not in as_done
    assert 'aria-label="Approval, Approve load plan' in html[documented:]
    assert ".back .seg, .gap .seg { border-style: dashed; }" in html
    assert "<dt>View</dt><dd>as done</dd>" in html and "<dt>Work type</dt>" in html
    for heading in ("Stories", "Strengths as stated (preserve)", "Work type and know-how",
                    "Official vs lived", "Glossary of SME terms", "Preserve / Improve",
                    "Reality gaps by gap class", "Disposition and value",
                    "System records"):  # fmt: skip
        assert html.count(f"<h3>{heading}</h3>") == 1, heading


def test_a_not_described_connector_is_drawn_dashed() -> None:
    from app.domain.graph import GraphEdge
    from tests.services.test_exports import sensemaking_data

    inp = sensemaking_data()
    done = inp.view_graphs["done"]
    on_map = md.steps(done)
    first, last = on_map[0], on_map[-1]
    gap = GraphEdge(id="gap-1", from_=first.id, to=last.id, kind="gap", label="Not described",
                    view_membership="done_only", provenance="I")  # fmt: skip
    done = done.model_copy(update={"edges": [*done.edges, gap]})
    inp = inp.model_copy(update={"view_graphs": {**inp.view_graphs, "done": done}})
    html = export_html.render_map_html(inp, TOKENS, FONTS)
    assert html.count('<div class="gap" aria-hidden="true">') == 1
    assert "a step the interview doesn't describe" in html  # the legend says what it means


def test_a_map_from_before_the_views_is_drawn_once() -> None:
    html = render()
    assert html.count('role="group" aria-label="Swimlane map"') == 1


def test_a_draft_says_it_is_not_validated_yet() -> None:
    """2026-10-28, Eric's draft map download: "validated by Owner" on a draft read as if someone
    had checked it. A published map keeps who validated it."""
    draft = render(published_at="")
    assert "Version v0.1 · not published yet · not validated yet" in draft
    assert "validated by" not in draft
    assert " · validated by Eric Yim</p>" in render()


def test_the_view_that_draws_more_comes_first_and_an_empty_view_says_why() -> None:
    """2026-10-28: as in the app (§3.12.11), the map from one manual leads with As documented; the
    empty As done map says why it has no steps instead of only a "Not described" line."""
    from tests.services.test_exports import sensemaking_data

    inp = sensemaking_data()
    documented = inp.view_graphs["documented"]
    empty = documented.model_copy(
        update={
            "elements": [el for el in documented.elements if el.kind not in md.STEP_KINDS],
            "edges": [],
        }
    )
    inp = inp.model_copy(update={"view_graphs": {"done": empty, "documented": documented}})
    html = export_html.render_map_html(inp, TOKENS, FONTS)
    done = html.index("<h3>Map as done: the work as actually performed</h3>")
    first = html.index("<h3>Map as documented: the documents&#x27; version</h3>")
    assert first < done < html.index("<h3>Steps</h3>")
    note = "No interview or system record describes these steps yet, so this view has none."
    assert html.count(note) == 1 and html.index(note) > done


def test_with_equal_views_as_done_comes_first_and_no_view_is_called_empty() -> None:
    from tests.services.test_exports import sensemaking_data

    inp = sensemaking_data()
    same = inp.view_graphs["done"]
    inp = inp.model_copy(update={"view_graphs": {"done": same, "documented": same}})
    html = export_html.render_map_html(inp, TOKENS, FONTS)
    assert html.index("<h3>Map as done") < html.index("<h3>Map as documented")
    assert "so this view has none" not in html


def test_facts_say_how_much_of_the_sources_is_about_other_flows() -> None:
    page = render(outside_flow_claims=6, outside_flow_questions=1)
    start = page.index('<section aria-labelledby="facts">')
    facts = page[start : page.index("Pain points as stated")]
    assert (
        "<p>6 claims and 1 question in these sources are about another flow, so they are kept off "
        "this map.</p>"
    ) in facts
    assert "another flow" not in render()


def test_a_role_with_several_letters_is_named_once() -> None:
    # Eric, 2026-10-30: "Cargo acceptance: Responsible; Cargo acceptance: Accountable" read twice.
    html = render()
    assert "<dt>Roles</dt><dd>Load controller: Responsible and Accountable</dd>" in html
    assert "Load controller: Responsible; Load controller: Accountable" not in html
    # A contested letter stays marked; each role still gets its own entry.
    assert (
        "<dd>Load controller: Responsible; Captain: Accountable (contested); "
        "Load control lead: Accountable (contested)</dd>"
    ) in html
    graph = sample_graph()
    step = next(el for el in graph.elements if el.label == "Draft load plan")
    step.raci = [*step.raci, step.raci[0].model_copy(update={"letter": "C"})]
    assert "Load controller: Responsible, Accountable and Consulted" in render(graph=graph)


def test_every_step_card_leads_back_to_the_map() -> None:
    # Eric, 2026-10-30: after clicking a step there was no way back up but scrolling.
    html = render()
    cards = re.findall(r'<article class="card step".*?</article>', html)
    assert len(cards) == len(md.steps(sample_graph()))
    back = '<p class="step__back"><a href="#interpretation">Back to the map</a></p>'
    assert all(card.endswith(back + "</article>") for card in cards)
    assert '<h2 id="interpretation">' in html
    assert ".step__back a { color: inherit;" in html  # the app's link style, no browser blue
