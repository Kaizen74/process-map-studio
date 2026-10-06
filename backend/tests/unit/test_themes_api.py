"""Emerging themes (API_CONTRACT.md → Emerging themes; Appendix E tier 3, criterion 58; C7b):
the sample's single-story proposal is left out; themes are listed with their stories, accepted,
renamed, dismissed or reopened by Eric (audited), and a re-run never touches his decisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db import session_scope
from app.domain.sensemaking import ThemeProposal
from app.repositories import claims as claims_repo
from app.repositories import themes as themes_repo
from app.repositories.tables import AuditRow
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def themes_url(d: Drafted) -> str:
    return f"/api/engagements/{d.engagement_id}/themes"


def plant(d: Drafted, *names: str) -> str:
    """Proposed themes resting on the sample's story (a test shortcut past S3c's checks)."""
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        story = next(cid for cid, r in claims_repo.verified_rows(session, d.version_id)
                     if r.claim_type == "story")  # fmt: skip
        themes_repo.replace_proposed(session, d.engagement_id, d.version_id, [
            ThemeProposal(theme=n, claim_ids=[story], basis="Both stories show it.")
            for n in names])  # fmt: skip
        return story


def theme_audit(d: Drafted) -> list[dict[str, Any]]:
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = session.scalars(select(AuditRow).where(AuditRow.target_type == "theme")
                               .order_by(AuditRow.created_at))  # fmt: skip
        return [{"action": r.action, "before": r.before, "after": r.after} for r in rows]


def test_the_sample_proposes_no_theme_from_a_single_story(drafted: Drafted) -> None:
    assert drafted.client.get(themes_url(drafted)).json() == []
    assert drafted.client.get("/api/engagements/nope/themes").status_code == 404


def test_themes_are_listed_with_their_stories_and_decided_by_eric(drafted: Drafted) -> None:
    story = plant(drafted, "Workarounds at peak times", "Paper slows the turnaround")
    listed = drafted.client.get(themes_url(drafted)).json()
    assert [(t["theme"], t["status"]) for t in listed] == [
        ("Workarounds at peak times", "proposed"),
        ("Paper slows the turnaround", "proposed"),
    ]
    fragment = listed[0]["fragments"][0]
    assert fragment["claim_id"] == story and fragment["fragment_type"] == "went_badly"
    assert fragment["text"] and fragment["anchor"]
    first, second = listed[0]["id"], listed[1]["id"]
    accepted = drafted.client.patch(f"/api/themes/{first}", json={"status": "accepted"})
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    renamed = drafted.client.patch(f"/api/themes/{first}", json={
        "status": "accepted", "theme": "  Busy-wave workarounds "}).json()  # fmt: skip
    assert renamed["theme"] == "Busy-wave workarounds"
    dismissed = drafted.client.patch(f"/api/themes/{second}", json={
        "status": "dismissed", "note": "Only one site"}).json()  # fmt: skip
    assert (dismissed["status"], dismissed["note"]) == ("dismissed", "Only one site")
    reopened = drafted.client.patch(f"/api/themes/{second}", json={"status": "proposed"}).json()
    assert reopened["status"] == "proposed"
    assert [a["action"] for a in theme_audit(drafted)] == [
        "Accepted emerging theme", "Renamed emerging theme", "Dismissed emerging theme",
        "Reopened emerging theme"]  # fmt: skip
    assert theme_audit(drafted)[1]["before"] == {"theme": "Workarounds at peak times"}
    # The same decision again changes nothing and writes no row.
    drafted.client.patch(f"/api/themes/{first}", json={"status": "accepted"})
    assert len(theme_audit(drafted)) == 4


def test_a_re_run_replaces_proposed_themes_and_keeps_decided_ones(drafted: Drafted) -> None:
    plant(drafted, "Workarounds at peak times", "Paper slows the turnaround")
    listed = drafted.client.get(themes_url(drafted)).json()
    drafted.client.patch(f"/api/themes/{listed[0]['id']}", json={"status": "dismissed"})
    plant(drafted, "A new pattern")  # what the next draft or refresh proposes
    after = drafted.client.get(themes_url(drafted)).json()
    assert [(t["theme"], t["status"]) for t in after] == [
        ("Workarounds at peak times", "dismissed"),
        ("A new pattern", "proposed"),
    ]


def test_the_rules_name_the_field(drafted: Drafted) -> None:
    plant(drafted, "Workarounds at peak times")
    theme = drafted.client.get(themes_url(drafted)).json()[0]["id"]
    terms = f"/api/engagements/{drafted.engagement_id}/redaction-terms"
    assert drafted.client.post(terms, json={"term": "Kestrel"}).status_code == 201
    for body, field in (
        ({"status": "maybe"}, "status"),
        ({"status": "accepted", "theme": "Violation at peak"}, "theme"),
        ({"status": "accepted", "theme": "Kestrel shortcuts"}, "theme"),
        ({"status": "accepted", "theme": ""}, "theme"),
        ({"status": "dismissed", "note": "x" * 501}, "note"),
    ):
        refused = drafted.client.patch(f"/api/themes/{theme}", json=body)
        assert refused.status_code == 422, refused.text
        assert refused.json()["error"]["details"]["field"] == field
        assert "Kestrel" not in refused.json()["error"]["message"]
    assert drafted.client.patch("/api/themes/nope", json={"status": "accepted"}).status_code == 404
    assert drafted.client.get(themes_url(drafted)).json()[0]["status"] == "proposed"
    assert theme_audit(drafted) == []
