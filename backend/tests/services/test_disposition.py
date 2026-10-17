"""Step disposition rules (PRD §3.15; criterion 91; R9a). Pure, no database."""

from __future__ import annotations

from dataclasses import replace

from app.services import disposition as d
from app.services.disposition import StepFacts

FLAG = {"component": "action", "input": "load plan", "output": "booking",
        "handoff": "load controller", "basis": "rule_based_automate_candidate"}  # fmt: skip
STEP = StepFacts(label="Issue load sheet", kind="activity", work_type="clear", mechanism="none",
                 flag=FLAG)  # fmt: skip


def test_each_rule_in_order() -> None:
    assert d.suggest(STEP) == (d.AUTOMATE, "Clear, rule-based work.")
    assert d.suggest(replace(STEP, flag=None))[1].endswith(d.NEEDS_FLAG_NOTE)
    reads = replace(STEP, flag={**FLAG, "component": "perception"})
    assert d.suggest(reads)[0] == d.AI_ASSISTED
    assert d.suggest(replace(STEP, work_type="complicated"))[0] == d.AI_ASSISTED
    assert d.suggest(replace(STEP, risk_flag="safety")) == (
        d.HUMAN_APPROVES, "Carries a safety risk: a person authorises it.")  # fmt: skip
    assert d.suggest(replace(STEP, kind="approval", mechanism="rule_based"))[0] == d.HUMAN_APPROVES
    assert d.suggest(replace(STEP, work_type="chaotic")) == (
        d.KEEP_HUMAN, "Chaotic work: it needs human judgment.")  # fmt: skip
    risky = replace(STEP, knowledge_risk="high", heuristics_share=0.5)
    assert d.suggest(risky)[1] == "High knowledge risk, mostly heuristics and experience."
    assert d.suggest(replace(risky, heuristics_share=0.4))[0] == d.AUTOMATE
    assert d.suggest(replace(STEP, work_type=None))[0] == d.KEEP_HUMAN
    judgment = replace(STEP, kind="decision", mechanism="judgment")
    assert d.suggest(judgment)[0] == d.KEEP_HUMAN  # clear but a judgment call: not automated


def test_delete_first_for_dead_controls_and_obsolete_rules() -> None:
    finding = replace(STEP, findings=[("reality_gap", "obsolete_rule", "Rule no longer applies")])
    assert d.suggest(finding) == (d.DELETE, "Gap finding: Rule no longer applies.")
    control = replace(STEP, kind="approval", source_state="documented_only", has_purpose=False,
                      no_record_in="DCS extract", work_type="complex")  # fmt: skip
    assert d.suggest(control)[0] == d.DELETE  # before keep human
    assert d.suggest(replace(control, has_purpose=True))[0] == d.KEEP_HUMAN
    assert d.suggest(replace(control, no_record_in=""))[0] == d.KEEP_HUMAN


def test_what_eric_may_choose() -> None:
    assert d.allowed(STEP) == d.ALL
    complex_step = replace(STEP, work_type="complex")
    assert d.refusal(complex_step, d.AUTOMATE) == "Complex work can't be automated or AI-assisted."
    assert d.refusal(replace(STEP, flag=None), d.AI_ASSISTED) == d.NO_FLAG
    assert d.refusal(replace(STEP, flag={**FLAG, "handoff": " "}), d.AUTOMATE) == d.NO_FLAG
    judgment = replace(STEP, kind="approval", mechanism="judgment")
    assert d.refusal(judgment, d.AUTOMATE) == d.JUDGMENT_RULES
    assert d.refusal(judgment, d.AI_ASSISTED) is None
    assert d.refusal(STEP, "outsource") == d.NOT_A_DISPOSITION
    assert d.allowed(replace(STEP, flag=None)) == [d.DELETE, d.HUMAN_APPROVES, d.KEEP_HUMAN]


def test_l10_checks_a_choice_against_the_map_as_it_is_now() -> None:
    assert d.lint_problem("clear", FLAG, d.AUTOMATE) == ""
    assert d.lint_problem("clear", None, d.AI_ASSISTED) == (
        "needs a complete AI flag for its disposition")  # fmt: skip
    assert d.lint_problem("complex", FLAG, d.AUTOMATE).startswith("is complex work")
    assert d.lint_problem("complex", None, d.KEEP_HUMAN) == ""
