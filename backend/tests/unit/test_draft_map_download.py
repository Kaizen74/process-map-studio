"""The draft map download (2026-10-28, Eric: "see the whole picture at any one time"): a draft's
interactive HTML map before any review, stamped as a draft. API_CONTRACT → GET
/versions/{vid}/export/{fmt}. Publishing still needs every step reviewed (constraint 8)."""

from __future__ import annotations

from tests.unit.test_documents_only_journey import documents_only
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["documents_only", "drafted"]

STAMP = "Draft: not reviewed, not published."


def test_a_draft_downloads_as_a_stamped_html_map(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/export/html"
    response = drafted.client.get(url)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="load-control-v0-1-draft-map.html"'
    )
    html = response.text
    assert STAMP in html and "0 of 10 steps reviewed" in html
    assert "Nothing in it is validated yet." in html
    assert html.count("Not reviewed yet") == 10  # each step's details say so
    assert "Priya" not in html  # names stay hidden (G10)
    assert "<img" not in html  # no pictures in any export (constraint 11)
    rows = [r for r in drafted.audit() if r["action"] == "Downloaded draft map"]
    assert len(rows) == 1
    ready = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/readiness").json()
    assert ready["nav"]["exports"] == "not_started"  # only a published export counts


def test_the_stamp_follows_the_review(drafted: Drafted) -> None:
    drafted.act("Draft load plan", "confirm")
    html = drafted.client.get(f"/api/versions/{drafted.version_id}/export/html").text
    assert "1 of 10 steps reviewed" in html and html.count("Not reviewed yet") == 9
    assert "Confirmed" in html


def test_other_formats_still_wait_for_publishing(drafted: Drafted) -> None:
    for fmt in ("md", "json", "csv"):
        response = drafted.client.get(f"/api/versions/{drafted.version_id}/export/{fmt}")
        assert response.status_code == 409, fmt


def test_the_published_map_carries_no_draft_stamp(drafted: Drafted) -> None:
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    html = drafted.client.get(f"/api/versions/{drafted.version_id}/export/html").text
    assert STAMP not in html and "Not reviewed yet" not in html


def test_a_documents_only_draft_with_open_problems_still_downloads(documents_only: Drafted) -> None:
    """Eric's case: a map from one manual, with exits the manual doesn't describe, can be seen
    whole and shared as a draft before anything is fixed."""
    d = documents_only
    html = d.client.get(f"/api/versions/{d.version_id}/export/html").text
    assert STAMP in html and "0 of 6 steps reviewed" in html
    for label in ("Draft load plan", "Return loading report", "Issue load sheet"):
        assert label in html
