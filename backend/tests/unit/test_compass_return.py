"""The `compass-return` file and suggested probes (2026-11-12, Eric's brief §2.4, §3 A and D;
DECISIONS 97). From a published version only; this app's own codes or the IDs exactly as received;
no quote, no person's name, no source file name and no key; the same content as JSON and as
readable text. An engagement made without a hand-off is refused in plain words and otherwise
works as before. Mocked: no key, no network."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.actions import interview as interview_action
from app.db import session_scope
from app.repositories import redaction as redaction_repo
from app.repositories.tables import Claim, Engagement, Source
from app.services import compass_return as rules
from app.services import grade
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_compass_handoff import handoff, start
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_roles_choose_remove import audit_actions

__all__ = ["drafted"]


def link_to_handoff(d: Drafted) -> dict[str, Any]:
    """Give the drafted sample the hand-off link an engagement started from VS-01 carries."""
    made = start(d.client)
    assert made.status_code == 201, made.text
    link = dict(made.json()["compass"])
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        row = session.get(Engagement, d.engagement_id)
        assert row is not None
        row.compass = link
    return link


def published(d: Drafted) -> dict[str, Any]:
    link = link_to_handoff(d)
    confirm_all(d)
    assert publish(d).status_code == 200
    return link


def download(d: Drafted, fmt: str = "json", cells: str = "") -> Any:
    extra = f"&cells={cells}" if cells else ""
    return d.client.get(f"/api/versions/{d.version_id}/compass-return?fmt={fmt}{extra}")


def message(response: Any) -> str:
    return str(response.json()["error"]["message"])


# --- When it is offered ---------------------------------------------------------------------


def test_only_a_published_version_of_a_hand_off_engagement_has_a_return_file(
    drafted: Drafted,
) -> None:
    link_to_handoff(drafted)
    draft = download(drafted)
    assert draft.status_code == 409
    assert message(draft) == (
        "Publish a version first: the return file is made from a published map."
    )
    assert drafted.client.get("/api/versions/nope/compass-return").status_code == 404


def test_without_a_hand_off_there_is_no_return_file_and_the_other_downloads_still_work(
    drafted: Drafted,
) -> None:
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    refused = download(drafted)
    assert refused.status_code == 409
    assert message(refused) == (
        "This engagement didn't start from a Capability Compass hand-off, so there is no "
        "engagement key to return findings under."
    )
    for fmt in ("md", "json", "csv", "html"):
        ordinary = drafted.client.get(f"/api/versions/{drafted.version_id}/export/{fmt}")
        assert ordinary.status_code == 200, ordinary.text


# --- What it holds --------------------------------------------------------------------------


def test_the_file_has_the_agreed_shape_and_this_apps_own_codes(drafted: Drafted) -> None:
    link = published(drafted)
    response = download(drafted)
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].endswith('-compass-return.json"')
    file = response.json()
    assert list(file) == ["format", "format_version", "generated_at", "source_app",
                          "engagement_key", "findings"]  # fmt: skip
    assert (file["format"], file["format_version"]) == ("compass-return", "1.0")
    assert (file["source_app"], file["engagement_key"]) == ("process-map-studio", link["key"])
    fields = ["ref", "kind", "title", "detail", "grade", "figure", "relates_to", "source_note"]
    for f in file["findings"]:
        assert list(f) == fields
        assert f["kind"] in rules.KINDS and f["grade"] in grade.GRADES
        assert isinstance(f["figure"], str) and f["source_note"]
        # The pilot and its cluster by default, exactly as received.
        assert f["relates_to"] == [link["pilot_ref"], link["cluster_ref"]]
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    steps = {e["code"]: e for e in graph["elements"] if e["code"]}
    returned = {f["ref"]: f for f in file["findings"] if f["kind"] == "step"}
    assert set(returned) == set(steps)
    for code, f in returned.items():
        step = steps[code]
        assert f["title"] == step["label"]
        work = step["work_type"] if step["work_type"] in rules.WORK_TYPES else None
        assert (f"Work type: {work}." if work else "Work type: not classified.") in f["detail"]
        if step["decision"]["mechanism"] in ("rule_based", "judgment"):
            words = {"rule_based": "rule-based", "judgment": "judgment"}
            assert f"Decided by {words[step['decision']['mechanism']]}." in f["detail"]
        assert f["grade"] == ("indicated" if step["provenance"] == "O" else "hypothesis")
    risks = [f for f in file["findings"] if f["kind"] == "knowledge_risk"]
    assert {f["ref"] for f in risks} == {c for c, e in steps.items() if e["k_risk"]}
    assert risks, "the sample has a knowledge risk"
    actions = [r["action"] for r in audit_actions(drafted.client, drafted.engagement_id)]
    assert "Exported compass-return" in actions


def test_eric_adds_cells_from_the_hand_off_and_no_other_id(drafted: Drafted) -> None:
    link = published(drafted)
    cell = link["cell_refs"][0]
    file = download(drafted, cells=cell).json()
    assert all(f["relates_to"] == [link["pilot_ref"], link["cluster_ref"], cell]
               for f in file["findings"])  # fmt: skip
    stranger = download(drafted, cells="CAP-99.People")
    assert stranger.status_code == 422
    assert message(stranger) == "Choose cells from this engagement's hand-off."
    assert download(drafted, fmt="pdf").status_code == 422


def test_no_quote_name_source_name_or_key_is_in_the_file(drafted: Drafted) -> None:
    published(drafted)
    client = drafted.client
    quotes: set[str] = set()
    for element_id in drafted.ids.values():
        detail = client.get(f"/api/elements/{element_id}").json()
        quotes |= {ev["quote"] for ev in detail["evidence"] if ev.get("quote")}
    assert quotes, "the sample's steps have quoted evidence"
    sources = client.get(f"/api/engagements/{drafted.engagement_id}/sources").json()
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        names = [t.term for t in redaction_repo.list_terms(session, drafted.engagement_id,
                                                           ["manual", "speaker_map"])]  # fmt: skip
    assert "Priya Nair" in names
    for fmt in ("json", "md"):
        text = download(drafted, fmt=fmt).text
        assert not [q for q in quotes if q in text]
        assert not [n for n in names if n.lower() in text.lower()]
        assert not [s["filename"] for s in sources if s["filename"] in text]
        assert "sk-" + "ant" not in text and "api_key" not in text.lower()
        assert str(handoff()["charter"]["thesis"]) not in text  # nor the charter's own prose


def test_the_readable_text_says_the_same_as_the_json(drafted: Drafted) -> None:
    link = published(drafted)
    file = download(drafted).json()
    text = download(drafted, fmt="md")
    assert text.status_code == 200 and text.headers["content-type"].startswith("text/markdown")
    body = text.text
    assert f"Engagement key: {link['key']} · pilot: {link['pilot_ref']}" in body
    assert f"Relates to: {link['pilot_ref']}, {link['cluster_ref']}" in body
    for f in file["findings"]:
        assert f"- **{f['ref']}** {f['title']} · {grade.WORDS[f['grade']]}" in body
        assert f"  Rests on: {f['source_note']}" in body


def test_a_verdict_on_what_is_tested_goes_back_under_the_id_as_received(drafted: Drafted) -> None:
    client = drafted.client
    link_to_handoff(drafted)
    added = client.post(f"/api/engagements/{drafted.engagement_id}/testing",
                        json={"ref": "H1", "text": "Late notices drive the rework.",
                              "refuted_by": "Rework without a late notice."})  # fmt: skip
    assert added.status_code == 201, added.text
    set_ = client.patch(f"/api/testing/{added.json()['id']}",
                        json={"verdict": "supported", "evidence_refs": ["S-03"],
                              "note": "Seen at the special loads check."})  # fmt: skip
    assert set_.status_code == 200, set_.text
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    [verdict] = [f for f in download(drafted).json()["findings"]
                 if f["kind"] == "hypothesis_verdict"]  # fmt: skip
    assert (verdict["ref"], verdict["title"]) == ("H1", "Late notices drive the rework.")
    assert verdict["detail"] == "Supported. Behind it: S-03. Seen at the special loads check."
    assert verdict["grade"] == "indicated"  # as sure as S-03, the step it rests on
    assert verdict["source_note"] == "The owner's verdict, resting on S-03."


def test_with_reality_views_on_discrepancies_go_back_with_their_figure_and_grade(
    drafted: Drafted,
) -> None:
    client = drafted.client
    on = client.put("/api/settings/modules", json={"reality_views_enabled": True})
    assert on.status_code == 200, on.text
    published(drafted)
    snapshot = client.get(f"/api/versions/{drafted.version_id}/reality").json()
    found = [f for f in download(drafted).json()["findings"] if f["kind"] == "discrepancy"]
    assert {f["ref"] for f in found} == {c["code"] for c in snapshot["codes"]}
    for f in found:
        code = next(c for c in snapshot["codes"] if c["code"] == f["ref"])
        assert f["grade"] == code["grade"]["grade"]  # the same grade the Reality view shows
        assert f["figure"] == f"{code['delta']['text']} ({code['delta']['label']})"
        assert f["title"] == code["title"]


# --- The rules, on their own ----------------------------------------------------------------


def inputs(**changes: Any) -> rules.Inputs:
    base: dict[str, Any] = {
        "engagement_key": "MERIDIAN", "pilot_ref": "VS-01", "cluster_ref": "CAP-04",
        "cells": [], "generated_at": "2026-11-12T09:00:00+00:00",
        "process_name": "Bid to contract renewal", "version_label": "v1.0",
    }  # fmt: skip
    return rules.Inputs(**(base | changes))


def test_discrepancies_and_intent_are_written_from_what_was_computed() -> None:
    x1 = rules.Discrepancy(
        code="X1", title="Approval skipped on a busy wave", types=["D3"], figure="38% of cases",
        figure_label="measured", grade="confirmed", grade_by_owner=False, impact="Control",
        verdict="correct", documents=1, interviews=2, system_cases=412)  # fmt: skip
    i1 = rules.Intent(code="I1", text="Every deviation is approved before release.",
                      kind="control_objective", result="not_met", target="100% of cases",
                      quoted=True)  # fmt: skip
    tested = rules.Tested(ref="P2", text="Controls hold under load.", verdict="refuted",
                          evidence_refs=["X1"], note="")  # fmt: skip
    found = rules.findings(inputs(discrepancies=[x1], intents=[i1], tested=[tested]))
    by_ref = {f["ref"]: f for f in found}
    assert by_ref["X1"] == {
        "ref": "X1", "kind": "discrepancy", "title": "Approval skipped on a busy wave",
        "detail": "Types: D3. Impact: Control. Verdict: correct the practice.",
        "grade": "confirmed", "figure": "38% of cases (measured)",
        "relates_to": ["VS-01", "CAP-04"],
        "source_note": "Rests on 1 document, 2 interviews, system records of 412 cases.",
    }  # fmt: skip
    assert (by_ref["I1"]["detail"], by_ref["I1"]["figure"]) == ("Not met.", "100% of cases")
    assert by_ref["I1"]["source_note"].startswith("Quoted from a policy or charter")
    assert by_ref["P2"]["grade"] == "confirmed"  # every finding behind it is confirmed
    assert by_ref["P2"]["detail"] == "Refuted. Behind it: X1."
    open_item = rules.Tested(ref="P3", text="Not looked at yet.", verdict="open",
                             evidence_refs=[], note="")  # fmt: skip
    [waiting] = rules.findings(inputs(tested=[open_item]))
    assert (waiting["grade"], waiting["source_note"]) == ("hypothesis", "No verdict yet.")
    assert json.loads(rules.render_json(inputs()))["findings"] == []
    assert "No finding to return yet." in rules.render_text(inputs())


def test_a_hidden_name_or_anything_shaped_like_a_key_is_caught_before_the_file_leaves() -> None:
    marker = "sk-" + "ant-"
    assert rules.leaks("Checked by priya nair.", ["Priya Nair"], (marker,)) == ["Priya Nair"]
    assert rules.leaks(f"token {marker}abc", [], (marker,)) == [marker]
    assert rules.leaks("Load controller checks the plan.", ["Priya Nair"], (marker,)) == []


# --- Suggested probes -----------------------------------------------------------------------


def test_the_hand_offs_prompts_are_offered_as_probes_and_never_become_evidence(
    client: TestClient,
) -> None:
    made = start(client).json()
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        probes = interview_action.suggested_probes(session, made["id"])
        assert probes == made["compass"]["interview_prompts"] and probes
        # A prompt is a prompt: no source, no claim and so no step comes from it.
        assert session.query(Source).filter_by(engagement_id=made["id"]).count() == 0
        assert session.query(Claim).count() == 0
        first_word = probes[0].split()[0]
        redaction_repo.add(session, engagement_id=made["id"], term=first_word,
                           replacement="a role", origin="manual")  # fmt: skip
        assert probes[0] not in interview_action.suggested_probes(session, made["id"])
    alone = client.post("/api/engagements", json={"name": "Load control"}).json()
    with session_scope(sessions) as session:
        assert interview_action.suggested_probes(session, alone["id"]) == []
