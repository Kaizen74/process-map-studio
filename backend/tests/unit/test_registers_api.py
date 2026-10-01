"""Registers and the cause library (API_CONTRACT.md → GET /versions/{vid}/registers, Cause library;
PRD §4 Views, §5.4 Registers, §6.3 P9) on the illustrative Appendix A draft, Claude mocked."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete

from app.actions import causes as causes_action
from app.db import session_scope
from app.repositories.tables import CauseLibraryEntry
from tests.services.test_lint import element
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_add import add
from tests.unit.test_review_refresh import ids_by_label, refresh

__all__ = ["drafted"]


def registers(d: Drafted, version_id: str | None = None) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{version_id or d.version_id}/registers")
    assert response.status_code == 200, response.text
    return dict(response.json())


def library(d: Drafted) -> list[dict[str, Any]]:
    response = d.client.get(f"/api/engagements/{d.engagement_id}/cause-library")
    assert response.status_code == 200, response.text
    return list(response.json())


def sessions(d: Drafted) -> Any:
    return d.client.app.state.sessions  # type: ignore[attr-defined]


# --- Registers ---------------------------------------------------------------------------------


def test_the_registers_of_the_sample(drafted: Drafted) -> None:
    body = registers(drafted)
    assert [(k["label"], k["lane"]) for k in body["k_risk"]] == [
        ("Draft load plan", "Load controller")
    ]
    flags = {f["label"]: f for f in body["ai_flags"]}
    assert list(flags) == ["Special loads OK?", "Load and return LIR", "Issue load sheet"]
    assert (flags["Special loads OK?"]["mechanism"], flags["Special loads OK?"]["component"]) == (
        "rule_based",
        "reasoning",
    )
    groups = [
        (g["cause_type"], [c["text"] for c in g["constraints"]])
        for g in body["constraints_by_cause"]
    ]
    # B.9 order: system fragmentation before single point knowledge before capacity mismatch.
    assert [cause for cause, _ in groups] == [
        "system_fragmentation",
        "single_point_knowledge",
        "capacity_mismatch",
    ]
    assert groups[0][1] == [
        "The cargo terminal's notification often comes late",
        "The loading report is on paper and re-keyed",
        "The paper loading report gets lost or arrives late.",  # A.10 (C3): the named weakness
    ]
    assert body["external_practice"] == []
    # The two lists the review tabs already show come back unchanged.
    assert (
        body["questions"]
        == drafted.client.get(f"/api/versions/{drafted.version_id}/questions").json()
    )
    assert (
        body["rejected_claims"]
        == drafted.client.get(f"/api/versions/{drafted.version_id}/rejected-claims").json()
    )
    assert "Priya" not in str(body)


def test_key_constraints_come_first_and_uncaused_ones_last(drafted: Drafted) -> None:
    plain = {"text": "Printer jams at stand 12", "cause_type": None}
    caused = {"text": "DCS is slow at peak", "cause_type": "system_fragmentation"}
    edited = drafted.client.patch(
        f"/api/elements/{drafted.ids['Issue load sheet']}",
        json={
            "constraints": [
                {**plain, "is_key": False, "provenance": "O"},
                {**caused, "is_key": False, "provenance": "O"},
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    groups = registers(drafted)["constraints_by_cause"]
    assert groups[-1]["cause_type"] is None
    assert [c["text"] for c in groups[-1]["constraints"]] == ["Printer jams at stand 12"]
    fragmentation = next(g for g in groups if g["cause_type"] == "system_fragmentation")
    # A.10 (C3): + the weakness the Ramp duty manager names, not a key constraint.
    assert [c["is_key"] for c in fragmentation["constraints"]] == [True, True, False, False]


def test_recommended_steps_and_rejected_steps(drafted: Drafted) -> None:
    added = add(
        drafted,
        label="Weigh bags at check-in",
        provenance="R",
        r_reference="IATA AHM 510, section 2",
    )
    assert added.status_code == 201, added.text
    assert registers(drafted)["external_practice"] == [
        {
            "element_id": added.json()["id"],
            "label": "Weigh bags at check-in",
            "r_reference": "IATA AHM 510, section 2",
        }
    ]
    drafted.act("Draft load plan", "reject")
    body = registers(drafted)
    assert body["k_risk"] == []
    assert "Draft load plan" not in {
        c["label"] for g in body["constraints_by_cause"] for c in g["constraints"]
    }


def test_unknown_versions_are_404(drafted: Drafted) -> None:
    missing = drafted.client.get("/api/versions/nope/registers")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "That version doesn't exist."


# --- Cause library -----------------------------------------------------------------------------


def test_contested_steps_get_one_pending_entry_per_divergence(drafted: Drafted) -> None:
    entries = library(drafted)
    assert [(e["element_label"], e["divergence_type"]) for e in entries] == [
        ("Load and return LIR", "threshold"),
        ("Deviation in limits?", "ownership"),
    ]
    lir, deviation = entries
    assert (
        lir["pattern"]
        == "Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice."
    )
    # A cause only from the step's own constraint with a cause type (key first); an inference.
    assert (lir["inferred_cause"], lir["cause_type"], lir["provenance"]) == (
        "The loading report is on paper and re-keyed",
        "system_fragmentation",
        "I",
    )
    # No constraint explains the ownership divergence: not known yet, never a guess.
    assert (deviation["inferred_cause"], deviation["cause_type"], deviation["provenance"]) == (
        "",
        None,
        "O",
    )
    assert {e["validation_result"] for e in entries} == {"pending"}
    assert lir["element_id"] == drafted.ids["Load and return LIR"]
    assert "Priya" not in str(entries)


def test_confirming_refuting_and_reopening_an_entry(drafted: Drafted) -> None:
    lir = library(drafted)[0]
    url = f"/api/cause-library/{lir['id']}"
    confirmed = drafted.client.patch(url, json={"validation_result": "confirmed"})
    assert confirmed.status_code == 200 and confirmed.json()["validation_result"] == "confirmed"
    assert drafted.client.patch(url, json={"validation_result": "refuted"}).status_code == 200
    assert drafted.client.patch(url, json={"validation_result": "pending"}).status_code == 200
    actions = [row["action"] for row in drafted.audit()[:3]]
    assert actions == ["Reopened cause", "Refuted cause", "Confirmed cause"]
    wrong = drafted.client.patch(url, json={"validation_result": "maybe"})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["details"]["field"] == "validation_result"
    unknown = drafted.client.patch(
        "/api/cause-library/nope", json={"validation_result": "confirmed"}
    )
    assert unknown.status_code == 404
    assert drafted.client.get("/api/engagements/nope/cause-library").status_code == 404


def test_refresh_adds_nothing_twice_and_keeps_validation(drafted: Drafted) -> None:
    lir = library(drafted)[0]
    drafted.client.patch(f"/api/cause-library/{lir['id']}", json={"validation_result": "confirmed"})
    assert refresh(drafted)["status"] == "done"
    after = library(drafted)
    assert len(after) == 2
    assert after[0]["validation_result"] == "confirmed"
    # The entry follows the step to its fresh successor on the refreshed map.
    assert after[0]["element_id"] == ids_by_label(drafted)["Load and return LIR"]


def test_a_reopened_draft_points_entries_at_its_own_steps(drafted: Drafted) -> None:
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    reopened = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen").json()
    graph = drafted.client.get(f"/api/versions/{reopened['id']}/graph").json()
    lir = next(e["id"] for e in graph["elements"] if e["label"] == "Load and return LIR")
    assert library(drafted)[0]["element_id"] == lir


def test_rejected_steps_get_no_entry(drafted: Drafted) -> None:
    with session_scope(sessions(drafted)) as session:
        session.execute(delete(CauseLibraryEntry))
    drafted.act("Load and return LIR", "reject")
    with session_scope(sessions(drafted)) as session:
        assert causes_action.collect(session, drafted.version_id) == 1
        assert causes_action.collect(session, drafted.version_id) == 0  # never twice
    assert [e["element_label"] for e in library(drafted)] == ["Deviation in limits?"]


def test_the_pattern_falls_back_to_plain_words() -> None:
    step = element("plan", "activity", source_state="contested", divergence_types=[])
    assert causes_action._pattern(step) == "The sources disagree about “Plan”."
    assert causes_action._cause(step) == ("", "")
