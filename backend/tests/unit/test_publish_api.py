"""Publish, reopen, versions and exports (API_CONTRACT.md → Versions, publish and exports; PRD §3.5,
§5.9, §7.2, §7.3) on the illustrative Appendix A draft, Claude mocked."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.db import session_scope
from app.domain.graph import MergeProposalRecord
from app.repositories import elements as map_repo
from app.repositories.tables import Image
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

STRUCTURAL = ("Flight scheduled", "Final load sheet issued")


def confirm_all(d: Drafted) -> None:
    for label, element_id in d.ids.items():
        if label not in STRUCTURAL:
            assert d.client.post(f"/api/elements/{element_id}/confirm").status_code == 200


def publish(d: Drafted, version_id: str | None = None) -> Any:
    return d.client.post(f"/api/versions/{version_id or d.version_id}/publish")


def sessions(d: Drafted) -> Any:
    return d.client.app.state.sessions  # type: ignore[attr-defined]


def test_publishing_is_refused_with_every_blocker(drafted: Drafted) -> None:
    drafted.act("Resolve or offload", "reject")  # "Special loads OK?" loses its No exit (L4)
    with session_scope(sessions(drafted)) as session:
        claims = map_repo.element_claims(session, drafted.version_id)
        ids = claims[drafted.ids["Draft load plan"]] + claims[drafted.ids["Issue load sheet"]]
        proposal = MergeProposalRecord(
            claim_ids=ids, proposed_label="Plan and issue", similarity=0.5
        )
        map_repo.add_merge_proposals(session, drafted.version_id, [proposal])
        map_repo.update_element(session, drafted.ids["Approve deviation"], {"needs_check": True})
        session.add(
            Image(element_id=drafted.ids["Draft load plan"], stored_path="x", origin="extracted")
        )
    response = publish(drafted)
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "PUBLISH_BLOCKED"
    blockers = error["details"]["blockers"]
    assert error["message"] == f"This draft can't be published yet: {len(blockers)} things to fix."
    types = [b["type"] for b in blockers]
    assert types.count("unreviewed_element") == 7  # 8 steps, one rejected
    assert types.count("needs_check") == 1 and types.count("pending_merge") == 1
    assert types.count("suggested_image") == 1
    lint = next(b for b in blockers if b["type"] == "lint_failure")
    assert lint["id"] == "L4" and lint["element_id"] == drafted.ids["Special loads OK?"]
    unreviewed = next(b for b in blockers if b["type"] == "unreviewed_element")
    assert unreviewed["message"] == "“Draft load plan” hasn't been reviewed yet."
    assert unreviewed["element_id"] == drafted.ids["Draft load plan"]
    assert drafted.client.get(f"/api/versions/{drafted.version_id}").json()["state"] == "draft"


def test_a_green_draft_publishes_as_v1_0_and_never_changes(drafted: Drafted) -> None:
    confirm_all(drafted)
    response = publish(drafted)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["label"], body["state"], body["published_by"]) == ("v1.0", "published", "Owner")
    assert body["published_at"] and body["quality_card"]["all_green"] is True
    assert body["review"] == {"reviewed": 8, "total": 8}
    assert [e["change"] for e in body["change_log"]] == ["confirmed"] * 8
    assert body["change_log"][0]["step"] == "Draft load plan"
    # Published versions never change.
    assert drafted.act("Draft load plan", "reject").status_code == 409
    assert drafted.client.patch(f"/api/elements/{drafted.ids['Draft load plan']}",
                                json={"kpi": "x"}).status_code == 409  # fmt: skip
    again = publish(drafted)
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "Only the current draft can be published."
    assert drafted.audit()[0]["action"] == "Published version"
    card = drafted.client.get(f"/api/versions/{drafted.version_id}/quality-card").json()
    assert card == body["quality_card"]
    ready = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/readiness").json()
    assert ready["nav"]["published"] == "done" and ready["nav"]["review"] == "done"
    assert ready["nav"]["exports"] == "not_started"
    # A fresh draft from scratch would lose the review: reopen instead.
    fresh = drafted.client.post(f"/api/engagements/{drafted.engagement_id}/draft")
    assert fresh.status_code == 409
    assert "Reopen it as a new draft" in fresh.json()["error"]["message"]


def test_exports_of_a_published_version(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/export"
    draft = drafted.client.get(f"{url}/md")
    assert draft.status_code == 409
    assert draft.json()["error"]["message"] == "Publish a version with a green quality card first."
    confirm_all(drafted)
    publish(drafted)
    md = drafted.client.get(f"{url}/md")
    assert md.status_code == 200
    assert md.headers["content-type"] == "text/markdown; charset=utf-8"
    assert (
        md.headers["content-disposition"]
        == 'attachment; filename="load-control-v1-0-master-map.md"'
    )
    text = md.text
    assert text.startswith("# Load control — Master Process Map\n\nVersion v1.0 · published ")
    assert "validated by Owner" in text and "All hard checks green: yes." in text
    graph = json.loads(drafted.client.get(f"{url}/json").text)
    assert graph["version"]["quality_card"]["all_green"] is True
    rows = list(csv.reader(io.StringIO(drafted.client.get(f"{url}/csv").text.removeprefix("﻿"))))
    assert len(rows) == 9
    html = drafted.client.get(f"{url}/html")
    assert html.headers["content-disposition"].endswith('-map.html"')
    for body in (text, html.text, json.dumps(graph)):
        assert "Priya" not in body
    assert (
        drafted.client.get(f"{url}/pdf").json()["error"]["message"]
        == "Choose md, json, csv or html."
    )
    ready = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/readiness").json()
    assert ready["nav"]["exports"] == "done"


def test_reopen_copies_the_map_into_a_locked_draft_and_publishes_as_v1_1(drafted: Drafted) -> None:
    confirm_all(drafted)
    drafted.act("Resolve or offload", "reject")
    drafted.act("Resolve or offload", "restore")
    drafted.act("Resolve or offload", "confirm")
    publish(drafted)
    before = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    response = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen")
    assert response.status_code == 201, response.text
    draft = response.json()
    assert (draft["label"], draft["state"], draft["parent_version_id"]) == (
        "v1.1 draft", "draft", drafted.version_id)  # fmt: skip
    assert draft["review"] == {"reviewed": 8, "total": 8} and draft["change_log"] == []
    after = drafted.client.get(f"/api/versions/{draft['id']}/graph").json()
    assert shape(after) == shape(before)
    assert len(after["edges"]) == len(before["edges"])
    assert {e["review_status"] for e in after["elements"] if e["kind"] not in ("start", "end")} == {
        "confirmed"
    }
    questions = drafted.client.get(f"/api/versions/{draft['id']}/questions").json()
    assert len(questions) == 5
    # One draft at a time; only the latest published version reopens.
    again = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen")
    assert (
        again.json()["error"]["message"]
        == "There is already a draft. Review or refresh it instead."
    )
    step = next(e["id"] for e in after["elements"] if e["label"] == "Issue load sheet")
    assert (
        drafted.client.patch(f"/api/elements/{step}", json={"kpi": "Issued by T-10"}).status_code
        == 200
    )
    published = publish(drafted, draft["id"]).json()
    assert published["label"] == "v1.1"
    [entry] = published["change_log"]
    assert (entry["change"], entry["step"]) == ("edited", "Issue load sheet")
    versions = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/versions").json()
    assert [(v["label"], v["state"]) for v in versions] == [
        ("v1.1", "published"),
        ("v1.0", "superseded"),
    ]
    old = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen")
    assert old.json()["error"]["message"] == "Only the latest published version can be reopened."
    # The superseded version still exports.
    assert drafted.client.get(f"/api/versions/{drafted.version_id}/export/md").status_code == 200


def shape(graph: dict[str, Any]) -> list[tuple[Any, ...]]:
    """What a copy must keep of each element (IDs change)."""
    return sorted(
        (e["stable_key"], e["label"], e["kind"], len(e["raci"]), len(e["evidence"]),
         len(e["constraints"]), e["ai_flag"] is not None)
        for e in graph["elements"]
    )  # fmt: skip


def test_unknown_versions_are_404(drafted: Drafted) -> None:
    calls = [
        ("get", "/api/versions/nope"),
        ("post", "/api/versions/nope/publish"),
        ("post", "/api/versions/nope/reopen"),
        ("get", "/api/versions/nope/export/md"),
        ("get", "/api/engagements/nope/versions"),
    ]
    for method, url in calls:
        assert getattr(drafted.client, method)(url).status_code == 404, url


def test_every_version_carries_its_signal_strength(drafted: Drafted) -> None:
    # P12: from the sources the version was drafted from (the sample has an SOP: strong).
    listed = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/versions").json()
    assert listed[0]["signal"]["level"] == "strong" and listed[0]["signal"]["score"] == 3
    detail = drafted.client.get(f"/api/versions/{drafted.version_id}").json()
    assert detail["signal"]["label"] == "Strong"
