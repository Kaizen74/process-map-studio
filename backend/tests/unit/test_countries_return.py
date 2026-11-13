"""Findings back to the Compass and the printable comparison pages (2026-11-13, Eric's brief
§4.5-4.7 and acceptance tests 6 and 7; DECISIONS 98). Belmar's return file has its country and
its variation findings in the shape of the Compass's own sample; Arden's has none of them; the
pages hold only classed or kept differences, role names, and no name, quote or source text."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import compass_return as rules
from tests.countries_fixture import PERSON, Countries, build
from tests.paths import BACKEND_ROOT
from tests.unit.test_comparisons_api import APPROVE, CREDIT, DRAFT_PRICE, LEGAL, by_kind, paired
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_roles_choose_remove import audit_actions

SAMPLE = BACKEND_ROOT / "tests" / "fixtures" / "compass" / "countries"
FRONTEND = BACKEND_ROOT.parent / "frontend" / "tests" / "fixtures"
REASON = "Belmar kept its pre-merger delegation of authority."


@pytest.fixture()
def classed(client: TestClient) -> tuple[Countries, dict[str, Any]]:
    """Belmar compared with Arden: who decides classed Inherited (V1), the price time kept (V2),
    the credit check classed Chosen (V3), the lane difference dismissed, the legal review open."""
    c = build(client)
    view = paired(c)
    found = by_kind(view)

    def act(kind: tuple[str, str | None, str | None], **body: Any) -> None:
        url = f"/api/comparisons/{view['id']}/differences/{found[kind]['key']}"
        assert c.client.put(url, json=body).status_code == 200

    act(
        ("who_decides", APPROVE, APPROVE),
        action="class",
        reason_class="inherited",
        reason_note=REASON,
    )
    act(("work_time", DRAFT_PRICE, DRAFT_PRICE), action="keep")
    act(
        ("only_other", None, CREDIT),
        action="class",
        reason_class="chosen",
        reason_note="The Country manager checks credit before every offer.",
    )
    act(("who_does", APPROVE, APPROVE), action="dismiss", note="The same as who decides.")
    return c, view


def returned(c: Countries, version_id: str, fmt: str = "json", cells: str = "") -> Any:
    extra = f"&cells={cells}" if cells else ""
    response = c.client.get(f"/api/versions/{version_id}/compass-return?fmt={fmt}{extra}")
    assert response.status_code == 200, response.text
    return response


def sample() -> dict[str, Any]:
    return dict(json.loads((SAMPLE / "belmar_return_process_map_studio.json").read_text("utf-8")))


# --- Acceptance test 6 ------------------------------------------------------------------------


def test_belmars_file_has_its_country_and_variations_in_the_compass_shape(
    classed: tuple[Countries, dict[str, Any]],
) -> None:
    c, _ = classed
    response = returned(c, c.belmar_version, cells="CAP-04.Process")
    assert response.headers["content-disposition"].endswith(
        'filename="MERIDIANBE_compass_return.json"'
    )
    file = response.json()
    expected = sample()
    assert list(file) == list(expected)  # format … engagement_key, country, findings
    assert (file["engagement_key"], file["country"]) == ("MERIDIANBE", "Belmar")
    shape = {f["kind"]: list(f) for f in expected["findings"]}
    variations = [f for f in file["findings"] if f["kind"] == "variation"]
    assert [v["ref"] for v in variations] == ["V1", "V2", "V3"]  # the dismissed one has no code
    v1, v2, v3 = variations
    assert list(v1) == shape["variation"]
    assert v1 == {
        "ref": "V1",
        "kind": "variation",
        "title": "Approve the renewal price: approved by Country manager in Belmar, by Regional "
        "finance controller in Arden",
        "detail": f"Types: Different role. Step S-04 (Approve the renewal price). Reason: {REASON}",
        "grade": "indicated",
        "figure": "",
        "relates_to": ["VS-01", "CAP-04", "CAP-04.Process"],
        "source_note": "Compared between the two published maps of VS-01; Belmar's step rests on "
        "1 interview and 1 document; Arden's step rests on 1 interview and 1 "
        "document.",
        "topic": "decision_right",
        "reason_class": "inherited",
        "compared_with": "Arden",
    }
    # Kept without a reason: no reason_class at all (never "unknown" unless Eric chose it).
    assert list(v2) == [k for k in shape["variation"] if k != "reason_class"]
    assert v2["figure"] == "60 min in Belmar vs 120 min in Arden (stated)"
    assert v2["detail"] == "Types: Different work time. Step S-03 (Draft the renewal price)."
    assert (v3["topic"], v3["reason_class"]) == ("role_presence", "chosen")
    assert v3["detail"].startswith("Types: Only in Belmar. Step S-05 (Check the credit limit).")
    # The other kinds keep their shape, now with the readout page they belong on.
    for f in file["findings"]:
        assert f["kind"] in rules.KINDS and f["grade"] in ("confirmed", "indicated", "hypothesis")
        if f["kind"] == "step":
            assert f["topic"] == ("decision_right" if f["ref"] == "S-04" else "way_of_working")
        if f["kind"] in ("knowledge_risk", "hypothesis_verdict", "intent"):
            assert "topic" not in f
    assert not [f for f in file["findings"] if LEGAL in json.dumps(f) and f["kind"] == "variation"]


def test_ardens_file_repeats_none_of_them(classed: tuple[Countries, dict[str, Any]]) -> None:
    c, _ = classed
    file = returned(c, c.arden_version).json()
    assert (file["engagement_key"], file["country"]) == ("MERIDIAN", "Arden")
    assert not [f for f in file["findings"] if f["kind"] == "variation"]
    assert not [f for f in file["findings"] if f["ref"].startswith("V")]


def test_the_readable_text_and_no_names_or_quotes(
    classed: tuple[Countries, dict[str, Any]],
) -> None:
    c, _ = classed
    text = returned(c, c.belmar_version, fmt="md").text
    assert "Engagement key: MERIDIANBE · country: Belmar · pilot: VS-01" in text
    assert "## Differences from another country" in text
    assert "  Reason class: Inherited" in text and "  Compared with: Arden" in text
    as_json = returned(c, c.belmar_version).text
    for content in (text, as_json):
        assert not [p for p in PERSON.values() if p in content]
        assert "said the" not in content  # the interviews' wording (quotes) never leaves
        assert "interview_belmar" not in content and "sop_arden" not in content  # file names


def test_a_newer_belmar_version_returns_its_variations_once_refreshed(
    classed: tuple[Countries, dict[str, Any]],
) -> None:
    from tests.countries_fixture import republish

    c, view = classed
    newer = republish(c.client, c.belmar, c.belmar_version)
    assert not [f for f in returned(c, newer).json()["findings"] if f["kind"] == "variation"]
    assert c.client.post(f"/api/comparisons/{view['id']}/refresh").status_code == 200
    again = [f["ref"] for f in returned(c, newer).json()["findings"] if f["kind"] == "variation"]
    assert again == ["V1", "V2", "V3"]  # the same codes: they belong to the differences


def test_the_rules_give_topics_and_leave_reason_class_out_unless_classed() -> None:
    assert rules.discrepancy_topic(["approval"], ["D12", "D1"]) == "decision_right"
    assert rules.discrepancy_topic(["activity"], ["D12"]) == "way_of_working"
    assert rules.discrepancy_topic(["approval"], ["D3"]) == "way_of_working"
    base = {
        "engagement_key": "MERIDIANBE",
        "pilot_ref": "VS-01",
        "cluster_ref": "CAP-04",
        "cells": [],
        "generated_at": "2026-11-13T09:00:00+00:00",
        "process_name": "Bid to contract renewal",
        "version_label": "v1.0",
    }
    lone = rules.Variation(
        code="V4",
        kind="only_reference",
        title="Legal review: only in Arden",
        topic="way_of_working",
        step_code="",
        step_label="Legal review of terms",
        reason_class="unknown",
        reason_note="",
        grade="hypothesis",
        figure="",
        country="Belmar",
        compared_with="Arden",
        source_note="Compared.",
    )
    [found] = rules.findings(rules.Inputs(**base, variations=[lone]))
    assert found["reason_class"] == "unknown"  # chosen as "Not known yet": sent as unknown
    assert found["detail"] == (
        "Types: Only in Arden. Step not on this map (Arden's step: Legal review of terms)."
    )
    assert "country" not in rules.build(rules.Inputs(**base))  # no country, no header field


# --- Acceptance test 7: the printable pages ---------------------------------------------------


def test_the_printable_pages_hold_only_what_eric_classed_or_kept(
    classed: tuple[Countries, dict[str, Any]],
) -> None:
    c, view = classed
    for layout in ("a3", "slide"):
        response = c.client.get(f"/api/comparisons/{view['id']}/export?layout={layout}")
        assert response.status_code == 200, response.text
        assert response.headers["content-disposition"].endswith(
            f'bid-to-contract-renewal-belmar-vs-arden-{layout}.html"'
        )
        html = response.text
        sections = [s.split('"')[0] for s in html.split('data-section="')[1:]]
        assert sections == ["summary", "decides", "work", "only"]
        decides = html.split('data-section="decides"')[1].split('data-section="work"')[0]
        assert "V1" in decides and REASON in decides and "Inherited" in decides
        work = html.split('data-section="work"')[1].split('data-section="only"')[0]
        assert "60 min in Belmar vs 120 min in Arden (stated)" in work
        assert "Kept; no reason given yet" in work
        only = html.split('data-section="only"')[1]
        assert "Check the credit limit" in only and "Legal review of terms" not in only  # open
        assert "done by Country manager in Belmar" not in html  # dismissed: left out
        # Singular when there is one (Eric, 2026-11-13).
        assert (
            "3 differences classed or kept; 1 not classed yet (not printed); 1 dismissed as not a "
            "real difference (not printed)."
        ) in html
        assert not [p for p in PERSON.values() if p in html]
        assert "said the" not in html and "interview_" not in html
        assert "http://" not in html.replace("http://www.w3.org", "")
        if os.environ.get("PMS_UPDATE_GOLDEN") == "1":  # for the browser check (print, axe)
            (FRONTEND / f"comparison_pages_{layout}.html").write_text(html, encoding="utf-8")
        assert (FRONTEND / f"comparison_pages_{layout}.html").read_text(encoding="utf-8") == html
    bad = c.client.get(f"/api/comparisons/{view['id']}/export?layout=poster")
    assert bad.status_code == 422
    assert "Exported country comparison" in [r["action"] for r in audit_actions(c.client, c.belmar)]


def test_the_summary_line_is_singular_or_plural_as_the_counts_need() -> None:
    from app.domain.comparisons import ComparisonView, DifferenceCounts
    from app.services.export_comparison import _counted

    def line(printed: int, opened: int, dismissed: int) -> str:
        counts = DifferenceCounts(open=opened, dismissed=dismissed)
        view = ComparisonView.model_construct(counts=counts)
        return _counted(view, printed)

    assert line(1, 0, 1) == (
        "1 difference classed or kept; 0 not classed yet (not printed); 1 dismissed as not a "
        "real difference (not printed)."
    )
    assert line(2, 3, 2) == (
        "2 differences classed or kept; 3 not classed yet (not printed); 2 dismissed as not real "
        "differences (not printed)."
    )
