"""Refresh draft from sources (API_CONTRACT.md → POST /versions/{vid}/refresh; PRD §3.5 locking,
§6.3 P6 test "locked elements unchanged after refresh"). Illustrative Appendix A engagement,
Claude mocked: the fresh run gives the same map as the first draft, so every difference after
the refresh comes from the folding rules."""

from __future__ import annotations

from typing import Any

import pytest

from app.db import session_scope
from app.domain.result import Err, ErrorKind
from app.repositories import elements as map_repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_add import add, graph, lines, lint_rules, passage
from tests.unit.test_review_edit import element, patch
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]


def refresh(d: Drafted) -> dict[str, Any]:
    response = d.client.post(f"/api/versions/{d.version_id}/refresh")
    assert response.status_code == 202, response.text
    wait_for_jobs(d.client)
    return dict(d.client.get(f"/api/jobs/{response.json()['job_id']}").json())


def ids_by_label(d: Drafted) -> dict[str, str]:
    return {e["label"]: e["id"] for e in graph(d)["elements"]}


def without_phase_id(detail: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in detail.items() if k != "phase_id"}


def test_reviewed_steps_are_unchanged_and_the_rest_is_replaced(drafted: Drafted) -> None:
    drafted.act("Draft load plan", "confirm")
    patch(drafted, "Issue load sheet", {"label": "Issue final load sheet", "kpi": "By T-10"})
    drafted.act("Resolve or offload", "reject")
    added = add(drafted, segment_ids=[passage(drafted)]).json()
    questions_url = f"/api/versions/{drafted.version_id}/questions"
    first_question = drafted.client.get(questions_url).json()[0]
    drafted.client.patch(f"/api/questions/{first_question['id']}", json={"status": "answered"})
    reviewed = ["Draft load plan", "Issue load sheet", "Resolve or offload"]
    before = {label: without_phase_id(element(drafted, label)) for label in reviewed}
    before[added["label"]] = without_phase_id(added)
    unreviewed_before = ids_by_label(drafted)["Special loads OK?"]

    job = refresh(drafted)
    assert job["status"] == "done", job
    assert job["type"] == "refresh" and job["target_id"] == drafted.version_id
    # Requirement change 2026-09-30: the message also says what changed among unreviewed steps.
    assert job["message"].endswith(
        "4 steps you reviewed stayed as they were. "
        "The steps you hadn't reviewed came out the same as before."
    )

    # Same draft, next number; the claims behind the dropped twins aren't counted twice.
    state = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/draft").json()
    assert state["version"]["id"] == drafted.version_id and state["version"]["label"] == "v0.2"
    assert (
        state["summary"]["verified"] == 23
    )  # v1.10 sample: + the 22:30 official and lived accounts
    # Every reviewed step exactly as it was: same ID, fields, RACI, evidence, status.
    for label, detail in before.items():
        after = drafted.client.get(f"/api/elements/{detail['id']}").json()
        assert without_phase_id(after) == detail, label
    # The fresh twins of reviewed steps were dropped; the unreviewed steps are new.
    labels = [e["label"] for e in graph(drafted)["elements"]]
    assert labels.count("Draft load plan") == 1 and "Issue load sheet" not in labels
    assert len(labels) == 13  # 12 drafted (v1.10 A.5; one edited name) + the added step
    assert ids_by_label(drafted)["Special loads OK?"] != unreviewed_before
    # Lines around the reviewed steps stay; those into them from fresh steps are re-pointed.
    flow = lines(drafted)
    expected = {
        ("Flight scheduled", "Draft load plan", "sequence", ""),
        ("Draft load plan", "Check fuel figures", "sequence", ""),
        ("Check fuel figures", "Approve load plan", "sequence", ""),
        ("Approve load plan", "Draft load plan", "reject", "Rework"),
        ("Special loads OK?", "Resolve or offload", "no", "No"),
        ("Deviation in limits?", "Issue final load sheet", "yes", "Within limits"),
        ("Issue final load sheet", "Final load sheet issued", "sequence", ""),
    }
    assert expected <= flow
    assert ("Draft load plan", "Approve load plan", "sequence", "") not in flow  # Eric's lines win
    assert not any(a == b for a, b, _, _ in flow)
    assert lint_rules(drafted) == ["L4"]  # the rejected step still leaves "No" without a target
    # A question worded as one already answered stays answered.
    refreshed = drafted.client.get(questions_url).json()
    assert [q["status"] for q in refreshed if q["question"] == first_question["question"]] == [
        "answered"
    ]
    assert len(refreshed) == 8  # v1.10 A.9: + three "order not stated" questions, never twice
    row = drafted.audit()[0]
    assert row["action"] == "Refreshed draft from sources"
    # Requirement change 2026-09-30 (run records): both runs' records are kept in the audit row.
    assert row["after"].pop("changes") == {
        "kept": 4, "new_steps": [], "no_longer_drafted": [], "renamed": []
    }  # fmt: skip
    made_with = row["before"].pop("run_record")
    assert made_with is not None and made_with == row["after"].pop("run_record")
    assert made_with["verifier"] is True and made_with["instructions"]["S1_extract_interview"]
    assert (row["before"], row["after"]) == ({"label": "v0.1"}, {"label": "v0.2", "kept_steps": 4})
    cards = drafted.client.get("/api/engagements").json()
    [card] = [c for c in cards if c["id"] == drafted.engagement_id]
    assert card["latest_version"]["label"] == "v0.2"


def test_the_refresh_says_what_it_drafted_differently_among_unreviewed_steps(
    drafted: Drafted,
) -> None:
    """Drift between runs made at different times is shown, never silent: the earlier run is
    made to differ (one step named otherwise, one under a key the fresh run doesn't draft)."""
    drafted.act("Draft load plan", "confirm")
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        map_repo.update_element(session, drafted.ids["Special loads OK?"], {"label": "Loads OK?"})
        map_repo.update_element(
            session, drafted.ids["Approve deviation"], {"stable_key": "an-older-step"}
        )
    state = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/draft").json()
    assert state["last_refresh"] is None  # the newest job is the draft, not a refresh

    job = refresh(drafted)
    assert job["status"] == "done", job
    assert job["message"].endswith(
        "1 step you reviewed stayed as they were. Among the steps you hadn't reviewed: "
        "1 new step, 1 step no longer drafted, 1 renamed."
    )
    expected = {
        "kept": 1,
        "new_steps": ["Approve deviation"],
        "no_longer_drafted": ["Approve deviation"],
        "renamed": [{"before": "Loads OK?", "after": "Special loads OK?"}],
    }
    state = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/draft").json()
    assert state["last_refresh"] == expected
    assert drafted.audit()[0]["after"]["changes"] == expected


def test_a_failed_refresh_changes_nothing(
    drafted: Drafted, monkeypatch: pytest.MonkeyPatch
) -> None:
    drafted.act("Draft load plan", "confirm")
    before = graph(drafted)
    from app.pipeline import s4_assemble

    def broken(*_args: Any, **_kwargs: Any) -> Err:
        return Err(ErrorKind.AI_FORMAT, "Claude's answer for 'Building the map' didn't match.")

    monkeypatch.setattr(s4_assemble, "assemble", broken)
    job = refresh(drafted)
    assert job["status"] == "failed"
    assert graph(drafted) == before
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        assert versions_repo.building(session, drafted.engagement_id) == []
        assert versions_repo.get(session, drafted.version_id).label == "v0.1"  # type: ignore[union-attr]


def test_refresh_start_rules(drafted: Drafted) -> None:
    missing = drafted.client.post("/api/versions/nope/refresh")
    assert missing.status_code == 404
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        old = versions_repo.create(
            session, engagement_id=drafted.engagement_id, label="v1.0", state="published"
        )
        jobs_repo.create(
            session,
            engagement_id=drafted.engagement_id,
            job_type="refresh",
            target_id=drafted.version_id,
            stages=[],
        )
    stale = drafted.client.post(f"/api/versions/{old.id}/refresh")
    assert stale.json()["error"]["message"] == "Only the current draft can be refreshed."
    busy = drafted.client.post(f"/api/versions/{drafted.version_id}/refresh")
    assert busy.status_code == 409
    assert busy.json()["error"]["message"] == "A draft map is already being made."
    again = drafted.client.post(f"/api/engagements/{drafted.engagement_id}/draft")
    assert again.json()["error"]["message"] == "A draft map is already being made."
