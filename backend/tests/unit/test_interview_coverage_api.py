"""The coverage report on the drafted sample (PRD §3.12.8, criterion 50; Appendix A.8 "Coverage
report": KPIs missing; stories thin, no "went well" and no "surprise" story; official vs lived
covered for one step only; follow-up questions generated). Claude mocked."""

from __future__ import annotations

import json

from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def coverage(d: Drafted) -> dict[str, object]:
    response = d.client.get(f"/api/versions/{d.version_id}/coverage")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_a8_coverage_report(drafted: Drafted) -> None:
    report = coverage(drafted)
    dims = report["dimensions"]
    assert isinstance(dims, dict)
    assert {n: (d["status"], d["evidence_count"]) for n, d in dims.items()} == {
        "trigger": ("missing", 0),  # the interview starts at M2.2; nobody asked what set it off
        "end_point": ("thin", 1),
        "step_spine": ("thin", 7),  # two As done lines rest on the order of mentioning (A.9)
        "handoffs": ("covered", 2),
        "decisions_and_criteria": ("covered", 5),
        "approvals": ("thin", 1),
        "exceptions": ("thin", 1),
        "raci": ("covered", 4),
        "work_and_wait_time": ("covered", 5),
        "kpis": ("missing", 0),  # A.8
        "artefacts": ("covered", 2),
        "know_how": ("thin", 4),
        "stories": ("thin", 1),  # A.8
        "official_vs_lived": ("covered", 1),  # A.8: one step only
        "sme_terms": ("covered", 3),
    }
    assert dims["stories"]["note"] == "Not yet told: went well, surprise"
    assert dims["official_vs_lived"]["note"] == "Both accounts on 1 step: Load and return LIR"
    assert dims["know_how"]["note"] == "No know-how yet: Busy wave?, Approve deviation"
    asked = [(q["dimension"], q["question_id"], q["about"]) for q in report["follow_up_questions"]]  # type: ignore[attr-defined]
    assert asked == [
        ("trigger", "M2.1", ""),
        ("end_point", "M2.5", ""),
        ("step_spine", "M2.2",
         "Load and return LIR → Busy wave?; Read report at aircraft → Deviation in limits?"),
        ("approvals", "M7.2", ""),
        ("exceptions", "M2.6", ""),
        ("kpis", "M7.1", ""),
        ("know_how", "M4.8", "Busy wave?"),
        ("know_how", "M4.8", "Approve deviation"),
        ("stories", "M5.1", ""),
        ("stories", "M5.3", ""),
    ]  # fmt: skip
    kpi = report["follow_up_questions"][5]  # type: ignore[index]
    assert (
        kpi["question"] == "How do you know this went well — what's measured, and who looks at it?"
    )
    assert "Priya" not in json.dumps(report)


def test_coverage_errors(drafted: Drafted) -> None:
    missing = drafted.client.get("/api/versions/nope/coverage")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "That version doesn't exist."


def test_a_reopened_draft_keeps_the_coverage_of_its_version(drafted: Drafted) -> None:
    before = coverage(drafted)
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    reopened = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen")
    assert reopened.status_code == 201, reopened.text
    after = drafted.client.get(f"/api/versions/{reopened.json()['id']}/coverage").json()
    assert after["dimensions"] == before["dimensions"]
    assert after["follow_up_questions"] == before["follow_up_questions"]
