"""Run records and the refresh check (anti-drift; API_CONTRACT → Run record,
GET /versions/{vid}/refresh-check). Illustrative Appendix A engagement, Claude mocked."""

from __future__ import annotations

from typing import Any

from app.actions import run_records
from app.config import APP_VERSION
from app.db import session_scope
from app.domain.models import RunRecord
from app.repositories import versions as versions_repo
from app.services import prompts
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]


def check(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/refresh-check")
    assert response.status_code == 200, response.text
    return dict(response.json())


def record(**changes: Any) -> RunRecord:
    base = RunRecord(
        model="claude-opus-5-5",
        effort="high",
        verifier=True,
        instructions=prompts.instruction_versions(),
        app_version=APP_VERSION,
    )
    return base.model_copy(update=changes)


def test_a_draft_is_stamped_with_how_it_was_made_and_nothing_differs(drafted: Drafted) -> None:
    body = check(drafted)
    made = body["made_with"]
    assert made["instructions"] == prompts.instruction_versions()
    assert made["verifier"] is True and made["app_version"] == APP_VERSION
    assert made["model"] == body["now"]["model"]
    assert body["changes"] == []


def test_a_new_model_and_the_verifier_switched_off_are_both_named(drafted: Drafted) -> None:
    before = check(drafted)["made_with"]
    settings = {"model": "claude-sonnet-5-5", "effort": "high", "verifier_enabled": False}
    assert drafted.client.put("/api/settings/model", json=settings).status_code == 200
    body = check(drafted)
    assert body["made_with"] == before  # the record is what made the draft, not today's Settings
    assert body["changes"] == [
        f"The model changed: this draft was made with {before['model']}; "
        "a refresh now uses claude-sonnet-5-5.",
        "The independent verifier checked this draft, but it is now switched off in Settings, "
        "so fresh suggestions would reach the map without that second check.",
    ]


def test_a_refresh_stamps_the_run_it_was_made_with(drafted: Drafted) -> None:
    settings = {"model": "claude-opus-5-5", "effort": "high", "verifier_enabled": False}
    assert drafted.client.put("/api/settings/model", json=settings).status_code == 200
    assert check(drafted)["changes"]  # the draft was made with the verifier on
    response = drafted.client.post(f"/api/versions/{drafted.version_id}/refresh")
    assert response.status_code == 202, response.text
    wait_for_jobs(drafted.client)
    body = check(drafted)
    assert body["made_with"]["verifier"] is False and body["changes"] == []


def test_a_draft_made_before_run_records_says_it_cant_be_compared(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        versions_repo.set_run_record(session, drafted.version_id, {})
    body = check(drafted)
    assert body["made_with"] is None and body["changes"] == [run_records.NO_RECORD]


def test_an_unknown_version_is_404(drafted: Drafted) -> None:
    response = drafted.client.get("/api/versions/nope/refresh-check")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "That version doesn't exist."


def test_differences_in_plain_words() -> None:
    same = record()
    assert run_records.differences(same, record()) == []
    # Effort is compared only when both are known (a model without effort settings sends none).
    assert run_records.differences(same, record(effort=None)) == []
    assert run_records.differences(same, record(effort="medium")) == [
        "The effort setting changed from high to medium."
    ]
    assert run_records.differences(record(verifier=False), same) == [
        "The independent verifier was off for this draft and is now on, so fresh suggestions "
        "get a second check this draft didn't have."
    ]
    # Reworded drafting instructions are named; the gap analyses' own prompts don't matter here.
    newer = dict(same.instructions, S1_extract_interview="2", GA_internal="9")
    assert run_records.differences(same, record(instructions=newer)) == [
        "Claude's instructions changed since this draft was made (an app update): "
        "extracting steps from interviews (version 1 → 2)."
    ]
    missing = {k: v for k, v in same.instructions.items() if k != "S5_questions"}
    assert (
        "writing validation questions (version none → 1)"
        in run_records.differences(record(instructions=missing), same)[0]
    )
    assert run_records.differences(None, same) == [run_records.NO_RECORD]


def test_every_draft_is_stamped_with_the_codebook_version(drafted: Drafted) -> None:
    """PRD Appendix E: the codebook version is stamped on every draft (and shown per version)."""
    [version] = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/versions").json()
    assert version["codebook_version"] == prompts.instruction_versions()["codebook"] == "1"


def test_a_reopened_draft_keeps_how_its_content_was_made(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        reopened = versions_repo.create_reopened(
            session,
            engagement_id=drafted.engagement_id,
            label="v1.1 draft",
            parent_id=drafted.version_id,
        )
        assert versions_repo.run_record(session, reopened.id) == versions_repo.run_record(
            session, drafted.version_id
        )
        [row] = [
            r for r in versions_repo.rows(session, drafted.engagement_id) if r["id"] == reopened.id
        ]
        assert row["codebook_version"] == "1"
