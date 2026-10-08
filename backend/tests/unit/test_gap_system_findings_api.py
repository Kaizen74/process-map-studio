"""System-record findings in Analysis A (API_CONTRACT.md → gap-analyses/internal step 6; PRD
§3.13.6; criterion 88; R6): fixture A.11 imported into the drafted Appendix A sample, Claude
mocked."""

from __future__ import annotations

from typing import Any

from tests.unit.test_log_alignment_api import EXPECTED, UNRECORDED, import_log
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]
SYSTEM_TYPES = {"hidden_work", "offline_work", "sequence_drift", "estimate_gap", "measured_rework"}


def analyse(d: Drafted) -> dict[str, Any]:
    started = d.client.post(f"/api/versions/{d.version_id}/gap-analyses/internal")
    assert started.status_code == 202, started.text
    wait_for_jobs(d.client)
    job = d.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert job["status"] == "done", job
    report = d.client.get(f"/api/gap-analyses/{started.json()['analysis_id']}").json()
    return dict(report)


def system(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in report["findings"]
            if any(e["side"] == "system" for e in f["evidence"])]  # fmt: skip


def test_unconfirmed_proposals_add_no_finding(drafted: Drafted) -> None:
    import_log(drafted.client, drafted.engagement_id)
    assert system(analyse(drafted)) == []


def test_confirmed_alignment_gives_the_a11_system_findings(drafted: Drafted) -> None:
    d = drafted
    lid = import_log(d.client, d.engagement_id)
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"} for a, s in EXPECTED.items()
    ]
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows += [
        {"activity": "", "element_id": d.ids[s], "status": "no_system_record"} for s in UNRECORDED
    ]
    assert d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows}).status_code == 200
    report = analyse(d)
    found = {
        (f["finding_type"], tuple(e["label"] for e in f["elements"])): f for f in system(report)
    }
    hidden = found[("hidden_work", ("Deviation in limits?",))]
    assert hidden["severity"] == "high" and hidden["provenance"] == "O"
    assert hidden["title"] == "System records work the map doesn't show: Manual weight override"
    rework = found[("measured_rework", ("Draft load plan",))]
    assert "in 40 of 200 cases (20%" in rework["text"]
    assert ("offline_work", ("Read report at aircraft",)) in found
    # Claude's dead-control finding for the plan approval gains the system's silence (A.11).
    dead = found[("dead_control_candidate", ("Approve load plan",))]
    assert any(e["side"] != "system" for e in dead["evidence"])  # still Claude's finding
    assert (
        "System records: the DCS extract log has no record of Approve load plan in 200 cases."
        in dead["notes"]
    )
    kinds = {k for k, _ in found}
    assert "estimate_gap" not in kinds  # A.11: SOP 10 min vs about 14 min is within 50%
    assert "sequence_drift" not in kinds  # the system agrees with the map's order
    for f in system(report):
        for e in f["evidence"]:
            if e["side"] == "system":
                assert (e["source_name"], e["quote"], e["segment_id"]) == ("DCS extract", "", None)
    # The Markdown report names the system records as a side, with its stance.
    dismiss = {"disposition": "dismissed", "note": "Seen in the test"}
    for f in report["findings"] + report["questions"]:
        if f["verification_status"] != "rejected" and f["disposition"] == "open":
            decided = d.client.patch(f"/api/gap-findings/{f['id']}", json=dismiss)
            assert decided.status_code == 200, decided.text
    analysis = report["analysis"]["id"]
    assert d.client.post(f"/api/gap-analyses/{analysis}/finalise").status_code == 200
    exported = d.client.get(f"/api/gap-analyses/{analysis}/export")
    assert exported.status_code == 200, exported.text
    assert "  - System records: DCS extract (silent)" in exported.text  # no window was given
