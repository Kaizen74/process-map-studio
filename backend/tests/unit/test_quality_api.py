"""GET /versions/{vid}/quality-card and readiness blockers (API_CONTRACT.md → Draft; PRD §7.2) on
the illustrative Appendix A draft, Claude mocked: only "Fully reviewed" stands between the sample
draft and a green card, and the exports behind Q7-Q9 are the real ones (names hidden)."""

from __future__ import annotations

from typing import Any

from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def card(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/quality-card")
    assert response.status_code == 200, response.text
    return dict(response.json())


def readiness(d: Drafted) -> dict[str, Any]:
    return dict(d.client.get(f"/api/engagements/{d.engagement_id}/readiness").json())


def test_the_sample_draft_waits_only_on_review(drafted: Drafted) -> None:
    body = card(drafted)
    failing = {c["id"]: c["detail"] for c in body["checks"] if c["status"] == "fail"}
    assert failing == {"Q6": "8 steps not reviewed yet."}
    assert body["all_green"] is False
    assert {c["id"]: c["status"] for c in body["checks"]}["Q10"] == "pass"
    assert any("no time stated" in w for w in body["warnings"])
    assert "Priya" not in str(body)
    ready = readiness(drafted)
    assert ready["blockers_count"] == 1
    assert ready["nav"]["review"] == "attention" and ready["nav_counts"]["review"] == 8


def test_confirming_every_step_turns_it_green(drafted: Drafted) -> None:
    for label, element_id in drafted.ids.items():
        if label not in ("Flight scheduled", "Final load sheet issued"):
            response = drafted.client.post(f"/api/elements/{element_id}/confirm")
            assert response.status_code == 200, response.text
    body = card(drafted)
    assert body["all_green"] is True
    assert [c["status"] for c in body["checks"]] == ["pass"] * 10
    ready = readiness(drafted)
    assert ready["blockers_count"] == 0 and ready["nav"]["review"] == "done"


def test_rejecting_a_connecting_step_shows_the_orphan(drafted: Drafted) -> None:
    drafted.act("Resolve or offload", "reject")
    failing = {c["id"] for c in card(drafted)["checks"] if c["status"] == "fail"}
    assert "Q3" in failing  # "Special loads OK?" lost its labelled No exit


def test_an_unknown_version_is_404(drafted: Drafted) -> None:
    response = drafted.client.get("/api/versions/nope/quality-card")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "That version doesn't exist."
