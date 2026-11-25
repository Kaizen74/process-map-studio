"""Who decides and who is accountable (PRD §3.20; DECISIONS 110). Pure and deterministic.

- Decided by: the step's decider role, or its lane role when it names none.
- Accountable: the roles holding A in the step's RACI, joined with " / ". Contested when an A is
  contested ("A?") or two roles hold A.
- "Decides ≠ accountable": a decision or approval where some role holds A and the accountable text
  differs from the decider's name, compared as the Capability Compass compares them (ignoring case
  and punctuation).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.enums import ElementKind, PaperDecider
from app.domain.graph import GraphElement

DECIDING = frozenset({ElementKind.DECISION.value, ElementKind.APPROVAL.value})
JOIN = " / "
MAX_ROLE = 80
PAPER_HINT = "The documents name a different decider. Record a Different role discrepancy?"


@dataclass(frozen=True, slots=True)
class Rights:
    """One decision or approval: the three roles as the Compass reads them ("" when not known)."""

    on_paper: str
    decided_by: str
    accountable: str
    contested: bool

    @property
    def split(self) -> bool:
        """The one who decides is not the one accountable (only when some role holds A)."""
        return bool(self.accountable) and same(self.accountable) != same(self.decided_by)

    @property
    def paper_differs(self) -> bool:
        return bool(self.on_paper) and same(self.on_paper) != same(self.decided_by)


def same(text: str) -> str:
    """The Compass's comparison: case and punctuation ignored, spaces collapsed."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def decider_id(e: GraphElement) -> str | None:
    return e.decision.decider_role_id or e.lane_role_id


def rights(e: GraphElement, roles: Mapping[str, str]) -> Rights | None:
    """The three roles of a decision or approval; None for any other step."""
    if e.kind not in DECIDING:
        return None
    holders = [r for r in e.raci if r.letter == "A"]
    names = list(dict.fromkeys(roles.get(r.role_id, "") for r in holders))
    names = [n for n in names if n]
    paper = e.paper_decider
    on_paper = (
        roles.get(paper.role_id or "", "")
        if paper is not None and paper.status == PaperDecider.NAMED.value
        else ""
    )
    return Rights(
        on_paper=on_paper[:MAX_ROLE],
        decided_by=roles.get(decider_id(e) or "", "")[:MAX_ROLE],
        accountable=JOIN.join(names)[:MAX_ROLE],
        contested=bool(holders) and (any(r.contested for r in holders) or len(names) > 1),
    )


def paper_hint(e: GraphElement, roles: Mapping[str, str], has_different_role: bool) -> str:
    """The hint beside a decider on paper that differs from the one in practice, when the step has
    no Different role (D12) discrepancy. It only asks; it creates nothing."""
    found = rights(e, roles)
    if found is None or has_different_role or not found.paper_differs:
        return ""
    return PAPER_HINT


@dataclass(frozen=True, slots=True)
class RaciCounts:
    decisions: int
    paper_differs: int
    split: int
    contested: int


def raci_counts(steps: Sequence[GraphElement], roles: Mapping[str, str]) -> RaciCounts:
    """The line above the RACI matrix, over the decisions and approvals given."""
    found = [r for e in steps if (r := rights(e, roles)) is not None]
    return RaciCounts(
        decisions=len(found),
        paper_differs=sum(1 for r in found if r.paper_differs),
        split=sum(1 for r in found if r.split),
        contested=sum(1 for r in found if r.contested),
    )
