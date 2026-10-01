"""Gap analysis B, external best practice (API_CONTRACT.md → Gap analysis; PRD §3.11.2, Appendix
A.7 traps TE1-TE9, §6.3 P10) on the illustrative Appendix A draft, web search mocked."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from app.domain.result import Err, ErrorKind, Ok
from app.pipeline import gb_external
from app.services import ai_service, gap
from tests import fixture_engagement
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

LABELS = [
    "Draft load plan",
    "Approve load plan",
    "Special loads OK?",
    "Resolve or offload",
    "Load and return LIR",
    "Busy wave?",  # v1.10 A.5
    "Read report at aircraft",
    "Deviation in limits?",
    "Approve deviation",
    "Issue load sheet",
]


@pytest.fixture()
def setup(drafted: Drafted) -> Iterator[Drafted]:
    """The sample draft with the A.7 Setup (industry, adjacent industries, confidential terms)."""
    url = f"/api/engagements/{drafted.engagement_id}"
    assert drafted.client.patch(url, json=fixture_engagement.GAP_SETUP).status_code == 200
    yield drafted


def create(d: Drafted) -> dict[str, Any]:
    response = d.client.post(f"/api/versions/{d.version_id}/gap-analyses/external")
    assert response.status_code == 201, response.text
    return dict(response.json())


def patch(d: Drafted, gid: str, brief: dict[str, Any], confirmed: bool = True) -> Any:
    return d.client.patch(
        f"/api/gap-analyses/{gid}/brief", json={"brief": brief, "confirmed": confirmed}
    )


def research_on(d: Drafted, on: bool = True) -> None:
    response = d.client.put("/api/settings/research", json={"web_research_enabled": on})
    assert response.status_code == 200, response.text


def calls(d: Drafted) -> int:
    return int(d.client.get("/api/settings/usage").json()["totals"]["calls"])


def run(d: Drafted, gid: str) -> dict[str, Any]:
    response = d.client.post(f"/api/gap-analyses/{gid}/run")
    assert response.status_code == 202, response.text
    assert d.client.app.state.worker.drain(60)  # type: ignore[attr-defined]
    job = d.client.get(f"/api/jobs/{response.json()['job_id']}").json()
    report = d.client.get(f"/api/gap-analyses/{gid}")
    assert report.status_code == 200, report.text
    return {"job": job, **report.json()}


def approved(d: Drafted) -> str:
    """An analysis with the drafted brief confirmed as it stands, web research switched on."""
    started = create(d)
    gid = started["analysis"]["id"]
    assert patch(d, gid, started["brief"]["brief"]).status_code == 200
    research_on(d)
    return str(gid)


# --- The brief (no AI, nothing sent) -------------------------------------------------------------


def test_the_drafted_brief_is_generic_and_nothing_is_sent(setup: Drafted) -> None:
    before = calls(setup)
    body = create(setup)
    assert calls(setup) == before  # no AI call
    analysis, state = body["analysis"], body["brief"]
    assert (analysis["mode"], analysis["status"], analysis["job_id"]) == (
        "external",
        "brief_draft",
        None,
    )
    brief = state["brief"]
    assert brief == {
        "process_name": "Load control",
        "industry": "Aviation ground handling",
        "adjacent_industries": ["Air cargo", "Airport operations"],
        "region": "",
        "steps": LABELS,
        "questions": list(gap.DEFAULT_QUESTIONS),
        "max_searches": 10,
        "allowed_domains": [],
        "blocked_domains": [],
        "recency_years": 5,
    }
    assert state["text"] == gap.brief_text(gap.Brief.model_validate(brief))
    assert (state["confirmed"], state["scan"]) == (False, {"hits": []})
    # The report of a brief that hasn't run carries the brief and nothing else.
    report = setup.client.get(f"/api/gap-analyses/{analysis['id']}").json()
    assert report["brief"] == state and report["findings"] == [] and report["sources"] == []


def test_te5_a_brief_with_a_company_a_name_and_a_passage_is_blocked(setup: Drafted) -> None:
    started = create(setup)
    gid = started["analysis"]["id"]
    brief = started["brief"]["brief"]
    brief["steps"].append("Acme Ground Services asks Priya Nair to check it")
    brief["questions"].append(
        "Why is it that if something can't be accepted, the airline decides what to offload?"
    )
    saved = patch(setup, gid, brief)
    assert saved.status_code == 200, saved.text
    hits = saved.json()["brief"]["scan"]["hits"]
    assert [h["reason"] for h in hits] == [
        "A name from your list of names to hide",
        "A confidential term from Setup",
        "Words copied from your sources",
    ]
    assert [h["text"] for h in hits][:2] == ["Priya Nair", "Acme Ground Services"]
    research_on(setup)
    before = calls(setup)
    refused = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert refused.status_code == 409
    error = refused.json()["error"]
    assert error["code"] == "BRIEF_NOT_APPROVED"
    assert error["message"] == (
        "Remove the highlighted items from the brief before running the research."
    )
    assert len(error["details"]["hits"]) == 3
    assert calls(setup) == before  # nothing was sent


def test_an_unconfirmed_brief_or_research_switched_off_sends_nothing(setup: Drafted) -> None:
    started = create(setup)
    gid = started["analysis"]["id"]
    before = calls(setup)
    off = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert off.status_code == 409
    assert off.json()["error"]["code"] == "WEB_RESEARCH_DISABLED"
    assert off.json()["error"]["message"] == (
        "Web research is switched off. Turn it on in Settings first."
    )
    research_on(setup)
    unticked = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert unticked.status_code == 409
    assert unticked.json()["error"] == {
        "code": "BRIEF_NOT_APPROVED",
        "message": "Tick “This brief contains no confidential information” before running the "
        "research.",
        "details": {"request_id": unticked.json()["error"]["details"]["request_id"]},
    }
    assert calls(setup) == before


def test_a_confidential_term_added_later_blocks_the_run(setup: Drafted) -> None:
    gid = approved(setup)
    terms = [*fixture_engagement.GAP_SETUP["confidential_terms"], "Issue load sheet"]
    url = f"/api/engagements/{setup.engagement_id}"
    assert setup.client.patch(url, json={"confidential_terms": terms}).status_code == 200
    refused = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "BRIEF_NOT_APPROVED"
    report = setup.client.get(f"/api/gap-analyses/{gid}").json()
    assert report["brief"]["scan"]["hits"] == [
        {"text": "Issue load sheet", "reason": "A confidential term from Setup"}
    ]


def test_brief_rules(setup: Drafted) -> None:
    started = create(setup)
    gid = started["analysis"]["id"]
    brief = started["brief"]["brief"]
    both = patch(
        setup, gid, {**brief, "allowed_domains": ["iata.org"], "blocked_domains": ["x.com"]}
    )
    assert both.status_code == 422
    assert both.json()["error"]["message"] == "Use allowed domains or blocked domains, not both."
    assert patch(setup, gid, {**brief, "max_searches": 50}).status_code == 422
    assert patch(setup, gid, {**brief, "recency_years": 0}).status_code == 422
    assert patch(setup, gid, {**brief, "surprise": 1}).status_code == 422
    assert patch(setup, "nope", brief).status_code == 404
    internal = setup.client.post(f"/api/versions/{setup.version_id}/gap-analyses/internal")
    assert setup.client.app.state.worker.drain(60)  # type: ignore[attr-defined]
    other = patch(setup, internal.json()["analysis_id"], brief)
    assert other.status_code == 409
    assert setup.client.post("/api/versions/nope/gap-analyses/external").status_code == 404
    assert setup.client.post("/api/gap-analyses/nope/run").status_code == 404


# --- The research run on the traps (TE1-TE4, TE6-TE9) --------------------------------------------


def test_only_the_approved_brief_is_sent(setup: Drafted, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[ai_service.ResearchCall] = []
    real = ai_service.call_claude_with_web_search

    def spy(conn: ai_service.AiConnection, call: ai_service.ResearchCall) -> Any:
        sent.append(call)
        return real(conn, call)

    monkeypatch.setattr(gb_external.ai_service, "call_claude_with_web_search", spy)
    gid = approved(setup)
    body = run(setup, gid)
    [call] = sent
    assert call.brief == body["brief"]["text"]
    assert (call.max_uses, call.allowed_domains, call.blocked_domains) == (10, (), ())
    for private in ("Ramp loads the aircraft", "Priya", "Acme", "LC-07", "RP-02", "fifteen"):
        assert private not in call.brief


def test_the_traps_give_the_expected_report(setup: Drafted) -> None:
    graph_before = setup.client.get(f"/api/versions/{setup.version_id}/graph").json()
    body = run(setup, approved(setup))
    job = body["job"]
    assert job["status"] == "done", job
    assert job["type"] == "gap_external"
    assert [s["status"] for s in job["stages"]] == ["done"] * 5
    assert job["message"] == (
        "The external best-practice report is ready: 4 findings, 4 rejected findings, "
        "2 searches used. Some results may be missing: see the notes."
    )
    found = [
        (
            f["finding_type"],
            f["severity"],
            f["evidence_strength"],
            f["comparison"],
            [e["label"] for e in f["elements"]],
        )
        for f in body["findings"]
    ]
    assert found == [
        ("missing_control", "high", "strong", "different", ["Issue load sheet"]),
        # TE7: the link to a step that isn't on the map was removed; the finding is kept.
        ("decision_rights_difference", "high", "strong", "different", ["Deviation in limits?"]),
        ("time_or_threshold_benchmark", "medium", "strong", "absent", []),
        # TE4: a vendor or unknown source only → weak evidence, Low.
        ("technology_enabler", "low", "weak", "absent", ["Issue load sheet"]),
    ]
    assert {f["provenance"] for f in body["findings"]} == {"R"}
    notes = {f["finding_type"]: f["notes"] for f in body["findings"]}
    assert notes["missing_control"] == [gap.COMPLIANCE_NOTE]  # regulator material
    assert notes["decision_rights_difference"] == [gb_external.LINK_REMOVED, gap.COMPLIANCE_NOTE]
    assert notes["time_or_threshold_benchmark"] == notes["technology_enabler"] == []
    rejected = [
        (f["title"], f["rejection_guardrail"], f["rejection_reason"]) for f in body["rejected"]
    ]
    assert rejected == [
        ("Loading report return time as a KPI", "GX2", "source not returned by the search"),  # TE1
        ("Load controllers rotate shifts weekly", "GX1", "no source cited"),  # TE2
        (
            "Deviation decisions within 5 minutes",
            "GX3",
            "claim not found in the cited source text",
        ),  # TE3
        (
            "Final walk-round before departure",
            "GAV",
            "TE8: the excerpt is about a walk-round, not a separate step in this process.",
        ),  # TE8
    ]
    analysis = body["analysis"]
    assert analysis["status"] == "draft_report"
    assert analysis["notes"] == [
        gb_external.TOOL_ERRORS["max_uses_exceeded"],  # TE6: a partial report, no crash
        "Left out as not a gap (the map already does this): “Load plan approved before "
        "release”.",  # TE9
    ]
    assert analysis["counts"] == {"kept": 4, "rejected": 4, "open": 4, "needs_check": 0}
    assert body["search_count"] == 2 and body["usage"]["calls"] == 3
    assert [(s["domain"], s["tier"], s["returned_in_results"]) for s in body["sources"]] == [
        ("iata.org", "industry_association", True),
        ("easa.europa.eu", "regulator", True),
        ("loadplanning-software.example.com", "other", True),
        ("unlisted.example.org", "other", False),
    ]
    # The map is unchanged by the analysis (constraint 22).
    graph_after = setup.client.get(f"/api/versions/{setup.version_id}/graph").json()
    assert graph_after == graph_before


def test_external_evidence_carries_the_source_and_a_short_excerpt(setup: Drafted) -> None:
    body = run(setup, approved(setup))
    control = body["findings"][0]
    assert [
        (e["side"], e["citation_id"], e["tier"], e["page_age"], e["url"].split("/")[2])
        for e in control["evidence"]
    ] == [
        ("external", "c1", "industry_association", "March 2024", "www.iata.org"),
        ("external", "c2", "regulator", "January 2025", "www.easa.europa.eu"),
    ]
    for f in body["findings"] + body["rejected"]:
        for e in f["evidence"]:
            assert len(e["quote"].split()) <= 25 and e["segment_id"] is None
    assert "Priya" not in json.dumps(body)


def test_a_run_cannot_be_repeated_or_its_brief_changed(setup: Drafted) -> None:
    gid = approved(setup)
    run(setup, gid)
    brief = setup.client.get(f"/api/gap-analyses/{gid}").json()["brief"]["brief"]
    changed = patch(setup, gid, brief)
    assert changed.status_code == 409
    assert changed.json()["error"]["message"] == (
        "This analysis has already run. Start a new one to change the brief."
    )
    again = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert again.status_code == 409
    assert again.json()["error"]["message"] == (
        "This analysis has already run. Start a new one to run the research again."
    )


def test_web_search_off_for_the_organisation_fails_plainly_and_can_run_again(
    setup: Drafted, monkeypatch: pytest.MonkeyPatch
) -> None:
    gid = approved(setup)
    off = Err(ErrorKind.CONFLICT, ai_service.SEARCH_OFF, api_code=ai_service.SEARCH_OFF_CODE)
    monkeypatch.setattr(gb_external.ai_service, "call_claude_with_web_search", lambda *_a: off)
    body = run(setup, gid)
    assert body["job"]["status"] == "failed"
    assert body["job"]["error"] == ai_service.SEARCH_OFF
    assert body["analysis"]["status"] == "failed" and body["findings"] == []
    monkeypatch.undo()
    research_on(setup)
    again = run(setup, gid)
    assert again["job"]["status"] == "done" and len(again["findings"]) == 4


def test_with_the_verifier_off_it_is_skipped(setup: Drafted) -> None:
    body_ = {"model": "claude-opus-5-5", "effort": "high", "verifier_enabled": False}
    assert setup.client.put("/api/settings/model", json=body_).status_code == 200
    body = run(setup, approved(setup))
    assert body["job"]["stages"][3]["status"] == "skipped"
    assert {f["verifier_verdict"] for f in body["findings"]} == {"not_run"}
    # Without the verifier the walk-round (TE8) is kept: only the gate's rejections remain.
    assert [f["rejection_guardrail"] for f in body["rejected"]] == ["GX2", "GX1", "GX3"]


def test_one_analysis_at_a_time_per_version(setup: Drafted) -> None:
    from app.actions import gap as gap_action

    gid = approved(setup)
    sessions = setup.client.app.state.sessions  # type: ignore[attr-defined]
    queued = gap_action.start_internal(sessions, setup.version_id, lambda _j: None)
    assert isinstance(queued, Ok)  # queued, never run
    busy = setup.client.post(f"/api/gap-analyses/{gid}/run")
    assert busy.status_code == 409
    assert busy.json()["error"]["message"] == "A gap analysis is already running for this version."
