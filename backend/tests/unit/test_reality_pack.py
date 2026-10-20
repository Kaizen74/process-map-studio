"""The Reality pack (PRD §3.18.6, §7.4; criterion 117; P13d) on fixture A.12: only a published
version with a green quality card; one offline HTML file (no script, no image, no outside
request); the §7.4 structure with one view per page and the legend and data label on every page;
verdicts only in Recommendation and the Appendix; at most 2 callouts a view on 16:9 pages; every
printed figure the snapshot's (RQ9); no name from the redaction list and no interview quote; the
same file every time. No AI call is made."""

from __future__ import annotations

import re
from html import escape
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import ai_service, export_reality, wording
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_reality_api import publish, snapshot, switch

FACTS = ["rv1", "rv2", "rv4", "rv5", "rv6", "rv7"]
VERDICT_TEXT = re.compile(r"\((suggested|confirmed)\)|pack-verdict|Decide first")


def pack(client: TestClient, vid: str, layout: str = "a3") -> str:
    response = client.get(f"/api/versions/{vid}/reality/export", params={"layout": layout})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert f"reality-pack-{layout}.html" in response.headers["content-disposition"]
    return response.text


def pages(html: str) -> list[str]:
    """Each printed page's HTML (a page holds nested sections, so split on the page's own tag)."""
    return ['<section class="page' + p for p in html.split('<section class="page')[1:]]


def page_of(html: str, view: str) -> str:
    return next(p for p in pages(html) if f'data-view="{view}"' in p.split(">", 1)[0])


def section(html: str, name: str) -> str:
    """The HTML of one top-level part of the pack (facts, interpretation, recommendation)."""
    match = re.search(rf'<div data-section="{name}">(.*?)</div><div data-section=|'
                      rf'<div data-section="{name}">(.*?)</div><section class="page" '
                      rf'data-section="appendix"', html, re.S)  # fmt: skip
    assert match, name
    return match.group(1) or match.group(2)


@pytest.fixture()
def published(reality: Reality) -> Reality:
    switch(reality.engagement.client, True)
    publish(reality.engagement.client, reality.version_id)
    return reality


def test_only_a_published_version_with_a_green_card(reality: Reality) -> None:
    client, vid = reality.engagement.client, reality.version_id
    refused = client.get(f"/api/versions/{vid}/reality/export")
    assert refused.status_code == 409
    assert (
        refused.json()["error"]["message"] == "Publish a version with a green quality card first."
    )
    assert client.get("/api/versions/nope/reality/export").status_code == 404
    bad = client.get(f"/api/versions/{vid}/reality/export", params={"layout": "a4"})
    assert bad.status_code == 422 and bad.json()["error"]["details"]["field"] == "layout"


def test_one_offline_file_with_the_7_4_structure(
    published: Reality, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_ai(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the Reality pack called Claude")

    monkeypatch.setattr(ai_service, "call_claude", no_ai)
    client, vid = published.engagement.client, published.version_id
    for layout in ("a3", "slide"):
        html = pack(client, vid, layout)
        assert html.startswith("<!doctype html>")
        assert "default-src 'none'" in html  # the content security policy: nothing from outside
        assert not re.search(r"<script|<img|<image|<iframe|<link\b", html, re.I)
        assert not re.search(r"https?://", html)
        assert re.findall(r"url\((?!data:|#rs-hatch)", html) == []
        assert f'class="pack pack--{layout}"' in html
        size = "420mm 297mm" if layout == "a3" else "1920px 1080px"
        assert f"@page {{ size: {size}" in html
        # Cover, Facts (six views in order), Interpretation, Recommendation (Fix or keep), Appendix.
        assert html.index('data-section="cover"') < html.index('data-section="facts"')
        views = [v for _, v in re.findall(r'data-view="(\w+)" data-section="(\w+)"', html)]
        assert re.findall(r'data-view="(\w+)"', html) == [*FACTS, "rv3"]
        assert views == ["facts"] * 6 + ["recommendation"]
        assert html.index('data-section="interpretation"') < html.index('data-view="rv3"')
        assert html.index('data-view="rv3"') < html.index('data-section="appendix"')
        # Every page but the cover has the legend and the data label.
        printed = pages(html)
        # cover, six facts, interpretation, Fix or keep and Decide first, appendix
        assert len(printed) == 1 + 6 + 1 + 2 + 1
        s = snapshot(client, vid)
        for page in printed[1:]:
            assert 'class="reality-legend"' in page and s["data_label"] in page


def test_verdicts_only_in_recommendation_and_the_appendix(published: Reality) -> None:
    """As Q7 for the Master Process Map: facts and interpretation carry no verdict."""
    html = pack(published.engagement.client, published.version_id)
    assert not VERDICT_TEXT.search(section(html, "facts"))
    assert not VERDICT_TEXT.search(section(html, "interpretation"))
    assert VERDICT_TEXT.search(section(html, "recommendation"))
    appendix = html[html.index('data-section="appendix"') :]
    assert "(suggested)" in appendix or "(confirmed)" in appendix
    assert "for the control owner to confirm" in section(html, "interpretation")


def test_callouts_per_page_and_headlines_from_the_snapshot(published: Reality) -> None:
    client, vid = published.engagement.client, published.version_id
    s = snapshot(client, vid)
    for layout, most in (("a3", 3), ("slide", 2)):
        html = pack(client, vid, layout)
        for vid_ in [*FACTS, "rv3"]:
            page = page_of(html, vid_)
            view = s["views"][vid_]
            assert f'<p class="reality-view__headline">{view["headline"]}</p>' in page
            shown = page.count('<li class="callout')
            assert shown == min(most, len(view["callouts"])), (layout, vid_)


def test_every_printed_callout_names_its_impact_in_words(published: Reality) -> None:
    """Colour never carries the impact class alone (constraint 17): a callout drawn in an impact
    colour also shows that class's symbol and word, as in the legend (found by the comprehension
    pilot, 2026-10-19: readers couldn't tell a risk from lost time)."""
    client, vid = published.engagement.client, published.version_id
    words = {i["impact_class"]: i["word"] for i in snapshot(client, vid)["legend"]["impacts"]}
    seen = 0
    for layout in ("a3", "slide"):
        for kind, body in re.findall(r'<li class="callout callout--(\w+)">(.*?)</li>',
                                     pack(client, vid, layout), re.S):  # fmt: skip
            assert f'<span class="impact-word impact-word--{kind}">' in body, body
            assert '<svg class="impact-glyph' in body and words[kind] in body, body
            seen += 1
    assert seen


def test_every_printed_figure_is_the_snapshot_figure(published: Reality) -> None:
    """RQ9 (G17): the pack prints each figure with the ID and text it has in the snapshot, the
    Reality screen and Leadership."""
    client, vid = published.engagement.client, published.version_id
    html = pack(client, vid)
    s = snapshot(client, vid)
    printed = re.findall(r'data-figure="([^"]+)"[^>]*>([^<]*)<', html)
    assert len(printed) >= len(s["tiles"]) + len(s["codes"])
    for fid, text in printed:
        assert s["figures"][fid]["text"] == text.replace("&amp;", "&"), fid
    leadership = client.get(f"/api/versions/{vid}/leadership").json()["reality"]
    for tile in leadership["tiles"]:
        assert f'data-figure="{tile["figure"]["id"]}" class="metric-tile__number">' \
            f'{tile["figure"]["text"]}<' in html  # fmt: skip


def test_no_name_no_quote_no_banned_word_and_the_same_file_every_time(published: Reality) -> None:
    client, eid, vid = published.engagement.client, published.engagement.eid, published.version_id
    html = pack(client, vid)
    terms = [t["term"] for t in client.get(f"/api/engagements/{eid}/redaction-terms").json()]
    assert terms  # the fixture names its speakers
    text = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    for term in terms:
        assert term.casefold() not in text.casefold(), term
    assert wording.banned_words(re.sub(r"<[^>]+>", " ", text)) == []
    for source in client.get(f"/api/engagements/{eid}/sources").json():
        if source["kind"] != "interview_transcript":
            continue
        page = client.get(f"/api/sources/{source['id']}/segments").json()
        for seg in page["segments"]:
            words = seg["text"].strip()
            if len(words) > 40:
                assert words not in text, words[:60]
    assert pack(client, vid) == html  # deterministic
    rows = client.get(f"/api/versions/{vid}/audit").json()
    assert any(r["action"] == "Exported Reality pack" for r in rows)


@pytest.mark.parametrize(
    ("layout", "height", "legible"),
    [("a3", 848.0, True), ("a3", 852.0, True), ("a3", 853.0, False), ("a3", 988.0, False),
     ("slide", 863.0, True), ("slide", 864.0, False), ("slide", 988.0, False)],
)  # fmt: skip
def test_a_drawing_prints_only_when_its_text_stays_at_11_px(
    layout: str, height: float, legible: bool
) -> None:
    """Found by the P13d browser check (2026-10-16): a tall Reality stack printed at 9.6 px."""
    assert export_reality.legible(1600.0, height, layout) is legible
    assert export_reality.legible(1600.0, 200.0, layout)  # a short drawing is limited by width


def test_a_drawing_too_tall_to_print_legibly_is_printed_as_its_table(
    published: Reality, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vid = published.engagement.client, published.version_id
    s = snapshot(client, vid)
    normal = pack(client, vid)
    assert export_reality.AS_TABLE not in normal  # A.12's drawings all print legibly
    monkeypatch.setattr(export_reality, "ROOM", {"a3": (100.0, 100.0), "slide": (100.0, 100.0)})
    for layout in ("a3", "slide"):
        html = pack(client, vid, layout)
        for view in [*FACTS, "rv3"]:
            page = page_of(html, view)
            if s["views"][view]["availability"]["state"] == "missing":
                assert "pack-drawing" not in page
                continue
            assert export_reality.AS_TABLE in page and 'class="reality-canvas"' not in page
            for cell in s["views"][view]["table"]["columns"]:
                assert f"<th>{escape(cell)}</th>" in page, (view, cell)
            assert 'class="reality-legend"' in page and s["data_label"] in page


def test_switching_the_reality_views_on_changes_no_other_export(reality: Reality) -> None:
    """The Reality views are optional (P13): with them on, the four exports of a published version
    are the same files as with them off; only the pack is added."""
    client, vid = reality.engagement.client, reality.version_id
    switch(client, False)
    publish(client, vid)

    def exports() -> dict[str, str]:
        files = {}
        for fmt in ("md", "json", "csv", "html"):
            response = client.get(f"/api/versions/{vid}/export/{fmt}")
            assert response.status_code == 200, (fmt, response.text[:200])
            files[fmt] = response.text
        return files

    off = exports()
    switch(client, True)
    assert exports() == off
    assert pack(client, vid).startswith("<!doctype html>")
