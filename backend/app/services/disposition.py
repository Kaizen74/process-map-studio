"""Step disposition (PRD §3.15; criterion 91; constraint 7; R9a): the deterministic suggestion with
its reason, and the rules a choice must follow. Pure: the facts come in, words come out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import DecisionMechanism, ElementKind, StepDisposition
from app.services.sensemaking import NEVER_AUTOMATED

DELETE = StepDisposition.DELETE.value
AUTOMATE = StepDisposition.AUTOMATE_RULES.value
AI_ASSISTED = StepDisposition.AI_ASSISTED.value
HUMAN_APPROVES = StepDisposition.HUMAN_APPROVES.value
KEEP_HUMAN = StepDisposition.KEEP_HUMAN.value
ALL = [d.value for d in StepDisposition]
NEEDS_FLAG = {AUTOMATE, AI_ASSISTED}
RISK_FLAGS = ("none", "financial", "safety", "regulatory")
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
CONTROLS = DECIDING
DOCUMENTED_ONLY = "documented_only"
FLAG_FIELDS = ("component", "input", "output", "handoff", "basis")
READS_DOCUMENTS = "perception"  # B.11: the AI flag's component that reads the step's input
NEEDS_FLAG_NOTE = " Needs a complete AI flag before you can choose it."

NOT_A_DISPOSITION = "Choose one of the five dispositions."
NO_FLAG = "Add a complete AI flag first: component, input, output, handoff and basis."
JUDGMENT_RULES = "A judgment step can't be automated by rules."


@dataclass(frozen=True, slots=True)
class StepFacts:
    """What the suggestion and the choice rules read about one step."""

    label: str
    kind: str  # B.2
    work_type: str | None  # B.29
    mechanism: str  # B.6
    flag: dict[str, str] | None  # the AI flag's five fields, or None
    risk_flag: str = "none"
    source_state: str = "not_assessed"
    has_purpose: bool = True  # a KPI or a constraint states why the step is there
    intended: bool = False  # a confirmed intent statement covers the step (P13, §3.15)
    no_record_in: str = ""  # a log Eric confirmed has no record of the step ("" if none)
    knowledge_risk: str = "unknown"
    heuristics_share: float = 0.0  # heuristics and experience among its know-how items
    findings: list[tuple[str, str | None, str]] = field(default_factory=list)  # type, class, title


def flag_complete(flag: dict[str, str] | None) -> bool:
    return flag is not None and all(str(flag.get(f, "")).strip() for f in FLAG_FIELDS)


def _work(step: StepFacts) -> str:
    return (step.work_type or "").capitalize()


def suggest(step: StepFacts) -> tuple[str, str]:
    """The suggested disposition and its reason (§3.15; the first rule that applies)."""
    # A control the organisation still intends is never suggested for deletion (§3.15).
    for finding_type, gap_class, title in [] if step.intended else step.findings:
        if finding_type == "dead_control_candidate" or gap_class == "obsolete_rule":
            return DELETE, f"Gap finding: {title}."
    if (step.kind in CONTROLS and step.source_state == DOCUMENTED_ONLY and step.no_record_in
            and not step.has_purpose and not step.intended):  # fmt: skip
        return DELETE, (f"The documents describe it, no interview mentions it, the "
                        f"{step.no_record_in} log has no record of it and no purpose is "
                        "stated.")  # fmt: skip
    if step.work_type in NEVER_AUTOMATED:
        return KEEP_HUMAN, f"{_work(step)} work: it needs human judgment."
    if step.knowledge_risk == "high" and step.heuristics_share >= 0.5:
        return KEEP_HUMAN, "High knowledge risk, mostly heuristics and experience."
    if step.kind == ElementKind.APPROVAL.value:
        return HUMAN_APPROVES, "An approval: a person authorises it."
    if step.risk_flag in RISK_FLAGS[1:]:
        return HUMAN_APPROVES, f"Carries a {step.risk_flag} risk: a person authorises it."
    missing = "" if flag_complete(step.flag) else NEEDS_FLAG_NOTE
    if step.work_type == "complicated":
        return AI_ASSISTED, ("Complicated work: an AI agent can prepare it with expert "
                             "oversight." + missing)  # fmt: skip
    reads = (step.flag or {}).get("component") == READS_DOCUMENTS
    if step.work_type == "clear" and step.kind == ElementKind.ACTIVITY.value and reads:
        return AI_ASSISTED, "Clear work that needs documents read: an AI agent can read them." + (
            missing
        )
    rule_based = step.kind not in DECIDING or step.mechanism == DecisionMechanism.RULE_BASED.value
    if step.work_type == "clear" and rule_based:
        return AUTOMATE, "Clear, rule-based work." + missing
    return KEEP_HUMAN, "Work type not confirmed yet: kept human until it is."


def refusal(step: StepFacts, disposition: str) -> str | None:
    """Why Eric can't choose this disposition for this step (None: he can)."""
    if disposition not in ALL:
        return NOT_A_DISPOSITION
    if disposition in NEEDS_FLAG and step.work_type in NEVER_AUTOMATED:
        return f"{_work(step)} work can't be automated or AI-assisted."
    if (disposition == AUTOMATE and step.kind in DECIDING
            and step.mechanism == DecisionMechanism.JUDGMENT.value):  # fmt: skip
        return JUDGMENT_RULES
    if disposition in NEEDS_FLAG and not flag_complete(step.flag):
        return NO_FLAG
    return None


def allowed(step: StepFacts) -> list[str]:
    """The dispositions Eric may choose for this step, in B.41 order."""
    return [d for d in ALL if refusal(step, d) is None]


def lint_problem(work_type: str | None, flag: dict[str, str] | None, disposition: str) -> str:
    """L10 (§3.15): what is wrong with a chosen disposition on the map as it is now ("" if
    nothing). The step may have changed since Eric chose it (its work type, its AI flag)."""
    if disposition not in NEEDS_FLAG:
        return ""
    if work_type in NEVER_AUTOMATED:
        return f"is {work_type} work, so it can't be automated or AI-assisted"
    if not flag_complete(flag):
        return "needs a complete AI flag for its disposition"
    return ""
