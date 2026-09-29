"""Gap findings: Eric's decisions, finalising, the Markdown export, the step panel and the Master
Map's section 3 (API_CONTRACT.md → Gap analysis; PRD §3.11.3, §7.3, acceptance 45-46)."""

from __future__ import annotations

from typing import Any

from app.services import gap
from tests.unit.test_gap_external_api import approved, setup
from tests.unit.test_gap_external_api import run as run_external
from tests.unit.test_gap_internal_api import run as run_internal
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted", "setup"]


def decide(d: Drafted, fid: str, disposition: str, note: str = "", **more: Any) -> Any:
    body = {"disposition": disposition, "note": note, **more}
    return d.client.patch(f"/api/gap-findings/{fid}", json=body)


def by_type(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["finding_type"]: f for f in report["findings"]}


def roles(d: Drafted) -> dict[str, str]:
    listed = d.client.get(f"/api/engagements/{d.engagement_id}/roles").json()
    return {r["name"]: r["id"] for r in listed}


def audit_actions(d: Drafted) -> list[str]:
    return [row["action"] for row in d.client.get(f"/api/versions/{d.version_id}/audit").json()]


# --- Documents vs practice ----------------------------------------------------------------------


def test_a_finding_becomes_a_question_in_the_draft(drafted: Drafted) -> None:
    report = run_internal(drafted)
    threshold = by_type(report)["threshold_gap"]
    response = decide(drafted, threshold["id"], "added_question")
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["disposition"] == "added_question"
    assert saved["created_item_ref"].startswith("question:")
    questions = drafted.client.get(f"/api/versions/{drafted.version_id}/questions").json()
    added = next(q for q in questions if f"question:{q['id']}" == saved["created_item_ref"])
    assert (added["element_label"], added["reason"], added["status"]) == (
        "Load and return LIR",
        "gap_analysis",
        "open",
    )
    assert added["question"] == f"{threshold['title']}: which account is right in practice?"
    assert "Added gap finding as question" in audit_actions(drafted)
    again = decide(drafted, threshold["id"], "dismissed", "no")
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "This finding already has a decision."


def test_the_sme_question_keeps_its_wording(drafted: Drafted) -> None:
    [question] = run_internal(drafted)["questions"]
    saved = decide(drafted, question["id"], "added_question").json()
    questions = drafted.client.get(f"/api/versions/{drafted.version_id}/questions").json()
    added = next(q for q in questions if f"question:{q['id']}" == saved["created_item_ref"])
    assert added["question"] == question["question"]
    assert added["element_label"] == "Approve load plan"


def test_the_cause_library_gets_an_entry_once(drafted: Drafted) -> None:
    url = f"/api/engagements/{drafted.engagement_id}/cause-library"
    before = drafted.client.get(url).json()
    findings = by_type(run_internal(drafted))
    # The ownership divergence already has an entry (made with the draft): it is reused.
    ownership = decide(drafted, findings["ownership_mismatch"]["id"], "added_cause").json()
    existing = next(c for c in before if c["divergence_type"] == "ownership")
    assert ownership["created_item_ref"] == f"cause:{existing['id']}"
    # Undocumented work is an omission on "Resolve or offload": a new entry, observed.
    offload = decide(drafted, findings["undocumented_work"]["id"], "added_cause").json()
    after = drafted.client.get(url).json()
    assert len(after) == len(before) + 1
    new = after[-1]
    assert offload["created_item_ref"] == f"cause:{new['id']}"
    assert (new["element_label"], new["divergence_type"], new["provenance"]) == (
        "Resolve or offload",
        "omission",
        "O",
    )
    assert new["pattern"] == findings["undocumented_work"]["text"]
    assert new["validation_result"] == "pending"


def test_a_finding_becomes_eric_s_step_with_its_passages(drafted: Drafted) -> None:
    findings = by_type(run_internal(drafted))
    dead = findings["dead_control_candidate"]
    step = {
        "kind": "activity",
        "label": "Check the plan approval is recorded",
        "lane_role_id": roles(drafted)["Load control lead"],
        "after_element_id": drafted.ids["Approve load plan"],
    }
    response = decide(drafted, dead["id"], "added_step", step=step)
    assert response.status_code == 200, response.text
    element_id = response.json()["created_item_ref"].removeprefix("element:")
    detail = drafted.client.get(f"/api/elements/{element_id}").json()
    assert (detail["label"], detail["provenance"], detail["review_status"]) == (
        "Check the plan approval is recorded",
        "O",
        "added",
    )
    cited = {e["segment_id"] for e in dead["evidence"] if e["segment_id"]}
    assert {e["segment_id"] for e in detail["evidence"] if e["segment_id"]} == cited
    assert audit_actions(drafted)[:2] == [
        "Added step from gap finding",
        "Added step",
    ]  # newest first


def test_decision_rules(drafted: Drafted) -> None:
    report = run_internal(drafted)
    findings = by_type(report)
    fid = findings["threshold_gap"]["id"]
    no_note = decide(drafted, fid, "dismissed", "  ")
    assert no_note.status_code == 422
    assert no_note.json()["error"]["message"] == "Say why you're dismissing this finding."
    for wrong in ("open", "delete"):
        bad = decide(drafted, fid, wrong)
        assert bad.status_code == 422
        assert bad.json()["error"]["message"] == (
            "Choose added_question, added_cause, added_step or dismissed."
        )
    no_step = decide(drafted, fid, "added_step")
    assert no_step.status_code == 422
    assert no_step.json()["error"]["message"] == "Choose where the new step goes."
    # The SME question has no passage: an observed step needs one (the Add step rule).
    [question] = report["questions"]
    step = {
        "kind": "activity",
        "label": "Ask about approval",
        "lane_role_id": roles(drafted)["Load control lead"],
        "after_element_id": drafted.ids["Approve load plan"],
    }
    passage = decide(drafted, question["id"], "added_step", step=step)
    assert passage.status_code == 422
    assert decide(drafted, "nope", "dismissed", "x").status_code == 404
    long = decide(drafted, fid, "dismissed", "x" * 1001)
    assert long.status_code == 422
    dismissed = decide(drafted, fid, "dismissed", "The SOP is being rewritten.")
    assert dismissed.status_code == 200
    assert dismissed.json()["disposition_note"] == "The SOP is being rewritten."
    assert "Dismissed gap finding" in audit_actions(drafted)


def decide_all_internal(d: Drafted, report: dict[str, Any]) -> None:
    for f in report["findings"]:
        if f["finding_type"] == "undocumented_work":
            assert decide(d, f["id"], "added_cause").status_code == 200
        else:
            assert (
                decide(d, f["id"], "dismissed", "Checked with the process owner.").status_code
                == 200
            )
    for q in report["questions"]:
        assert decide(d, q["id"], "added_question").status_code == 200


def test_finalise_and_export(drafted: Drafted) -> None:
    report = run_internal(drafted)
    gid = report["analysis"]["id"]
    early = drafted.client.post(f"/api/gap-analyses/{gid}/finalise")
    assert early.status_code == 409
    assert early.json()["error"]["message"] == "Decide on every finding first: 5 still open."
    assert drafted.client.get(f"/api/gap-analyses/{gid}/export").status_code == 409
    decide_all_internal(drafted, report)
    final = drafted.client.post(f"/api/gap-analyses/{gid}/finalise")
    assert final.status_code == 200, final.text
    body = final.json()
    assert body["analysis"]["status"] == "finalised" and body["analysis"]["finalised_at"]
    assert body["analysis"]["counts"]["open"] == 0
    locked = decide(drafted, report["findings"][0]["id"], "added_question")
    assert locked.status_code == 409
    assert locked.json()["error"]["message"] == "This report is finalised and can't be changed."
    again = drafted.client.post(f"/api/gap-analyses/{gid}/finalise")
    assert again.json()["error"]["message"] == "Only a draft report can be finalised."
    assert "Finalised gap report" in audit_actions(drafted)

    exported = drafted.client.get(f"/api/gap-analyses/{gid}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")
    assert 'filename="gap-analysis-internal-v0.1.md"' in exported.headers["content-disposition"]
    md = exported.text
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "## 1. Facts",
        "## 2. Interpretation",
        "## 3. Recommendation",
        "## Rejected findings",
    ]
    assert md.startswith("# Load control — Gap analysis: documents vs practice\n")
    assert "- [O] Plan approval by the Load control lead is documented but never mentioned in " \
        "practice · High severity · steps: Approve load plan" in md  # fmt: skip
    assert "  - Documents: sop LC-07 §3.2 (supports); jd load control lead ¶ 2 (supports)" in md
    assert "  - Practice: interview transcript (silent)" in md
    assert "- Is the load plan approved by the Load control lead before release to Ramp, and if " \
        "not, why not? · Decision: added as a validation question" in md  # fmt: skip
    assert "Decision: dismissed (Checked with the process owner.)" in md
    assert "Decision: added to the cause library" in md
    # No passage's words, no names.
    for quoted in ("We sometimes wait fifteen minutes", "it's the captain who decides", "Priya"):
        assert quoted not in md
    assert md.split("## Rejected findings")[1].strip() == "None."


def test_the_step_panel_lists_the_findings_about_it(drafted: Drafted) -> None:
    report = run_internal(drafted)
    detail = drafted.client.get(f"/api/elements/{drafted.ids['Approve load plan']}").json()
    dead = by_type(report)["dead_control_candidate"]
    [question] = report["questions"]
    assert detail["gap_findings"] == [
        {
            "id": dead["id"],
            "analysis_id": report["analysis"]["id"],
            "mode": "internal",
            "title": dead["title"],
            "severity": "high",
            "disposition": "open",
        },
        {
            "id": question["id"],
            "analysis_id": report["analysis"]["id"],
            "mode": "internal",
            "title": "Cause not explained by the sources",
            "severity": None,
            "disposition": "open",
        },
    ]
    other = drafted.client.get(f"/api/elements/{drafted.ids['Issue load sheet']}").json()
    assert other["gap_findings"] == []


def test_a_finalised_report_appears_in_the_master_map(drafted: Drafted) -> None:
    report = run_internal(drafted)
    decide_all_internal(drafted, report)
    assert (
        drafted.client.post(f"/api/gap-analyses/{report['analysis']['id']}/finalise").status_code
        == 200
    )
    confirm_all(drafted)
    assert publish(drafted).status_code == 200, publish(drafted).text
    md = drafted.client.get(f"/api/versions/{drafted.version_id}/export/md").text
    section = md.split("### Gap analyses")[1]
    assert "- Documents vs practice · finalised " in section
    assert "· 2 accepted findings: Offload resolution is undocumented work; Cause not explained " \
        "by the sources" in section  # fmt: skip
    html = drafted.client.get(f"/api/versions/{drafted.version_id}/export/html").text
    assert "Documents vs practice · finalised " in html
    # Published and no draft: questions and steps wait for a new draft; causes don't.
    later = run_internal(drafted)
    findings = by_type(later)
    blocked = decide(drafted, findings["threshold_gap"]["id"], "added_question")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message"] == (
        "Reopen this map as a new draft first: questions and steps are added to the draft."
    )
    assert decide(drafted, findings["threshold_gap"]["id"], "added_cause").status_code == 200


# --- External best practice ---------------------------------------------------------------------


def test_external_decisions_and_export(setup: Drafted) -> None:
    report = run_external(setup, approved(setup))
    findings = by_type(report)
    control = findings["missing_control"]
    cause = decide(setup, control["id"], "added_cause")
    assert cause.status_code == 422
    assert cause.json()["error"]["message"] == (
        "Only documents-vs-practice findings go to the cause library."
    )
    rejected = decide(setup, report["rejected"][0]["id"], "dismissed", "x")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["message"] == "A rejected finding can't be used."
    step = {
        "kind": "approval",
        "label": "Second-person check of the load sheet",
        "lane_role_id": roles(setup)["Load controller"],
        "after_element_id": setup.ids["Issue load sheet"],
        "mechanism": "rule_based",
    }
    added = decide(setup, control["id"], "added_step", step=step)
    assert added.status_code == 200, added.text
    element_id = added.json()["created_item_ref"].removeprefix("element:")
    detail = setup.client.get(f"/api/elements/{element_id}").json()
    source = control["evidence"][0]
    assert (detail["provenance"], detail["r_reference"], detail["source_state"]) == (
        "R",
        f"{source['source_name']} {source['url']}",
        "not_assessed",
    )
    for f in report["findings"]:
        if f["id"] != control["id"]:
            assert decide(setup, f["id"], "added_question").status_code == 200
    gid = report["analysis"]["id"]
    assert setup.client.post(f"/api/gap-analyses/{gid}/finalise").status_code == 200
    md = setup.client.get(f"/api/gap-analyses/{gid}/export").text
    assert md.startswith("# Load control — Gap analysis: external best practice\n")
    assert "  - Illustrative industry guidance on load control (industry association, March " \
        "2024) https://www.iata.org/illustrative/load-control-guidance: “The load sheet shall be " \
        "checked by a second qualified person before it is signed.”" in md  # fmt: skip
    assert "- [R] Second-person check of the load sheet before signing: different from the map: " \
        f"Issue load sheet · High severity. {gap.COMPLIANCE_NOTE}" in md  # fmt: skip
    assert "weak evidence (vendor or unknown sources only)" in md
    assert "Decision: added as a step" in md
    rejected_counts = md.split("## Rejected findings")[1].split("## Notes")[0].strip().splitlines()
    assert rejected_counts == [
        "- GAV (gap verifier): 1",
        "- GX1 (no source cited): 1",
        "- GX2 (source not returned by the search): 1",
        "- GX3 (claim not in the cited text): 1",
    ]
    notes = md.split("## Notes")[1]
    assert "The search limit was reached" in notes and "Left out as not a gap" in notes
    for line in md.splitlines():
        if "“" in line:
            quote = line.split("“")[1].split("”")[0]
            assert len(quote.split()) <= 25
    assert "Priya" not in md
