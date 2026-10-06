"""Lane-boundary findings (PRD Appendix F.4 L5, F.6 F1 and F4, criterion 76; C8): where the
interviews describe teams' activities overlapping or falling between them, recorded with the one
Responsible role the map keeps (constraint 5) and the others as Consulted, with a note.

Pure and deterministic: explicit inputs (each step, its lane role and its checked claims, names
already hidden by the caller), findings out. Never changes the map; the findings are questions
to settle with the teams.
"""

from __future__ import annotations

import re
from typing import Literal

from app.domain.sensemaking import BoundaryStep, LaneBoundaryFinding

Kind = Literal["shared_delivery", "gap", "boundary"]

BOUNDARY_QUESTIONS = ("L5", "F1", "F4")
# Words with which an SME says an activity belongs to no team ("it falls between us").
GAP_WORDS = re.compile(
    r"\b(?:nobody|no one|no-one|neither|falls? between|fell between|not clear who|no owner)\b",
    re.IGNORECASE,
)
F1 = (
    "Going back to where we left off, could you help me separate the activities managed by "
    "{a} versus {b}?"
)
F4 = "On “{step}”, how does your team work with {other}? It sounds like both show up together."


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for v in values:
        key = v.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(v.strip())
    return out


def lane_boundaries(steps: list[BoundaryStep]) -> list[LaneBoundaryFinding]:
    """One finding per step where the claims name more than one team doing the work (shared
    delivery), say it falls between teams (gap), or answer a boundary question (L5, F1, F4)."""
    findings = []
    for step in steps:
        lane = step.lane_role
        others = [r for r in _unique([c.responsible for c in step.claims])
                  if r.lower() != lane.lower()]  # fmt: skip
        asked = _unique([c.question_id for c in step.claims
                         if c.question_id in BOUNDARY_QUESTIONS])  # fmt: skip
        gap = any(c.question_id in ("L5", "F1") and GAP_WORDS.search(c.text) for c in step.claims)
        who = lane or "no role yet"
        kind: Kind
        if gap:
            kind = "gap"
            note = (f"The interviews say this falls between teams. The map keeps one Responsible "
                    f"({who}); confirm it with the teams.")  # fmt: skip
        elif others:
            kind = "shared_delivery"
            note = (f"Shared delivery: {', '.join(others)} also take part. One Responsible "
                    f"({who}), the others Consulted; confirm with the teams.")  # fmt: skip
        elif asked:
            kind = "boundary"
            note = "Discussed as a boundary between teams; confirm the Responsible role with both."
        else:
            continue
        findings.append(LaneBoundaryFinding(
            element_id=step.element_id, label=step.label, kind=kind, responsible=lane,
            consulted=others, note=note, question_ids=asked,
        ))  # fmt: skip
    return findings


def follow_up_question(finding: LaneBoundaryFinding, own_role: str = "") -> tuple[str, str]:
    """The F-series question for a finding (F.6), asked of an interviewee in `own_role`: F4 where
    teams share the work, F1 otherwise; "your team" is the interviewee's, the other team is the
    first of the step's roles that isn't theirs."""
    own = own_role.strip().lower()
    others = [r for r in [finding.responsible, *finding.consulted] if r and r.lower() != own]
    other = others[0] if others else "the other teams"
    if finding.kind == "shared_delivery" and others:
        return "F4", F4.format(step=finding.label, other=other)
    mine = own_role.strip() or finding.responsible or "your team"
    return "F1", F1.format(a=mine, b=other)
