"""R6: system-record findings for Analysis A (PRD §3.13.6; criterion 88; fixture A.11)."""

from __future__ import annotations

from typing import Any

from app.services import system_findings as rules
from app.services.system_findings import FindingStep, LogFacts, stated_minutes

PLAN = FindingStep("plan", "e-plan", "Draft load plan", "activity", "corroborated",
                   {"Stated": "About twenty minutes, around T-120"})  # fmt: skip
APPROVE = FindingStep("approve", "e-approve", "Approve load plan", "approval", "documented_only")
DEVIATION = FindingStep("deviation", "e-dev", "Deviation in limits?", "decision", "contested")
LIR = FindingStep("lir", "e-lir", "Load and return LIR", "activity", "contested",
                  {"SME": "Up to fifteen minutes' wait for the report",
                   "Documented": "Within 10 minutes of loading completion"})  # fmt: skip
READ = FindingStep("read", "e-read", "Read report at aircraft", "activity", "practiced_only")
STEPS = [PLAN, APPROVE, DEVIATION, LIR, READ]


def facts(**changes: Any) -> LogFacts:
    base: dict[str, Any] = {
        "log_id": "L1", "name": "DCS extract", "window": "2026-03-02 to 2026-04-26", "cases": 200,
        "matched": {"Plan created": "plan", "Plan revised": "plan",
                    "Weight deviation checked": "deviation", "Loading report received": "lir"},
        "hidden": ["Manual weight override"], "no_record": ["approve", "read"],
        "activity_cases": {"Plan created": 200, "Plan revised": 40, "Weight deviation checked": 200,
                           "Loading report received": 200, "Manual weight override": 23},
        "work_median": {"Plan created": 19.9, "Loading report received": 13.4},
        "transitions": [("Weight deviation checked", "Manual weight override", 23),
                        ("Plan created", "Plan revised", 40)],
        "step_figures": {"plan": {"cases": 200, "events": 240, "rework_cases": 40},
                         "lir": {"cases": 200, "events": 200, "rework_cases": 0}},
    }  # fmt: skip
    return LogFacts(**(base | changes))


def by_type(found: rules.SystemFindings) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for f in found.findings:
        out.setdefault(f.finding_type, []).append(f)
    return out


def test_minutes_are_read_from_each_accounts_own_words() -> None:
    assert stated_minutes("Within 10 minutes of loading completion") == 10
    assert stated_minutes("Up to fifteen minutes' wait for the report") == 15
    assert stated_minutes("About twenty minutes, around T-120") == 20  # an offset isn't a time
    assert stated_minutes("About forty minutes loading; up to fifteen minutes' wait") is None
    assert stated_minutes("Around T-15") is None


def test_a11_gives_the_findings_appendix_a11_expects() -> None:
    found = rules.findings(STEPS, [facts()], ai_dead=set())
    kinds = by_type(found)
    assert set(kinds) == {"hidden_work", "dead_control_candidate", "offline_work",
                          "measured_rework"}  # no estimate gap, no drift  # fmt: skip
    [hidden] = kinds["hidden_work"]
    assert (hidden.severity, hidden.element_ids) == ("high", ["e-dev"])  # after a decision
    assert hidden.text == (
        "The DCS extract log records “Manual weight override” in 23 of 200 cases (12%), mostly "
        "right after Deviation in limits?; no step on the map matches it."
    )
    [dead] = kinds["dead_control_candidate"]
    assert (dead.severity, dead.element_ids, dead.evidence[0].stance) == ("high", ["e-approve"],
                                                                          "silent")  # fmt: skip
    [offline] = kinds["offline_work"]
    assert (offline.element_ids, offline.severity) == (["e-read"], "low")
    [rework] = kinds["measured_rework"]
    assert rework.text.endswith("in 40 of 200 cases (20%; activities: Plan created, Plan revised).")
    for f in found.findings:
        assert (f.section, f.provenance, f.verifier_verdict) == ("fact", "O", "not_run")
        [ev] = f.evidence
        assert (ev.side, ev.source_kind, ev.source_name, ev.anchor, ev.quote, ev.segment_id) == (
            "system", "system_log", "DCS extract", "2026-03-02 to 2026-04-26", "", None,
        )  # fmt: skip


def test_claudes_dead_control_finding_gets_the_system_evidence_instead() -> None:
    found = rules.findings(STEPS, [facts()], ai_dead={"approve"})
    assert "dead_control_candidate" not in by_type(found)
    evidence, note = found.dead_control_support["approve"]
    assert evidence.stance == "silent"
    assert (
        note
        == "System records: the DCS extract log has no record of Approve load plan in 200 cases."
    )


def test_an_estimate_more_than_half_away_from_the_measured_time_is_a_finding() -> None:
    slow = facts(work_median={"Plan created": 19.9, "Loading report received": 24.0})
    sme, documents = by_type(rules.findings(STEPS, [slow], set()))["estimate_gap"]
    assert sme.element_ids == documents.element_ids == ["e-lir"] and sme.severity == "low"
    assert sme.text.startswith("SME time for Load and return LIR: “Up to fifteen minutes'")
    assert "(60% different)" in sme.text
    assert documents.text.startswith("Documented time for Load and return LIR: “Within 10 min")
    assert "median of 24 min" in documents.text and "(140% different)" in documents.text
    near = facts(work_median={"Loading report received": 20.0})  # 33% from 15, 100% from 10
    [only] = by_type(rules.findings(STEPS, [near], set()))["estimate_gap"]
    assert only.text.startswith("Documented time")
    untimed = facts(work_median={})  # without end times nothing is compared
    assert "estimate_gap" not in by_type(rules.findings(STEPS, [untimed], set()))


def test_a_contradicted_order_is_drift_high_on_a_decision() -> None:
    note = "The system records Deviation in limits? before Load and return LIR in 9 cases."
    found = by_type(rules.findings(STEPS, [facts(contradictions={"deviation": note})], set()))
    [drift] = found["sequence_drift"]
    assert (drift.severity, drift.evidence[0].stance) == ("high", "contradicts")
    assert drift.text == f"{note} The map puts it after."


def test_fewer_than_five_cases_and_low_rework_give_nothing() -> None:
    small = facts(cases=4, activity_cases={"Manual weight override": 4}, step_figures={},
                  work_median={})  # fmt: skip
    assert rules.findings(STEPS, [small], set()).findings == []
    tenth = {"plan": {"cases": 200, "events": 220, "rework_cases": 20}}
    steady = facts(hidden=[], no_record=[], step_figures=tenth)
    assert rules.findings(STEPS, [steady], set()).findings == []  # 10% is not above 10%
