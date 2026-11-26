"""The SOP register (PRD §3.20; DECISIONS 110): who owns and updates each SOP or manual, its review
dates and whether the copy in use is controlled. Pure and deterministic; `today` is given.

- The owner is a role (chosen), "other role" text Eric typed or checked, or free text typed before
  this register existed and not yet checked ("check: is this a role?").
- A review is overdue when its due date has passed (a partial date counts to the end of its month
  or year). The Capability Compass also flags a review or version older than 24 months; this app
  only sends the dates.
- A copy is uncontrolled only once Eric has set the flag (or it was already "yes": controlled).
- The same SOP uploaded twice (same title, ignoring case) keeps only the newest by version date in
  the register's counts and the return file; the older one is marked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.enums import SourceKind
from app.domain.graph import GraphElement
from app.domain.models import SourceView

KINDS = frozenset({SourceKind.SOP.value, SourceKind.MANUAL.value})


@dataclass(frozen=True, slots=True)
class Entry:
    source_id: str
    title: str
    kind: str
    owner: str  # the role's name or the other text; "" when not recorded
    owner_status: str  # role · other · check · none
    updated_by: str
    version_date: str
    last_reviewed: str
    review_due: str
    controlled: bool | None  # None: not known
    overdue: bool
    older: bool  # an older version of an SOP also in the sources


@dataclass(frozen=True, slots=True)
class Counts:
    sops: int
    without_owner: int
    without_updater: int
    overdue: int
    uncontrolled: int


def title_of(s: SourceView) -> str:
    return s.title.strip() or Path(s.filename).stem


def _end(date: str) -> str:
    """A partial date at the end of its period, comparable as text."""
    return {4: f"{date}-12-31", 7: f"{date}-31"}.get(len(date), date)


def _start(date: str) -> str:
    return {4: f"{date}-01-01", 7: f"{date}-01"}.get(len(date), date)


def entries(sources: Sequence[SourceView], roles: Mapping[str, str], today: str) -> list[Entry]:
    """The SOPs and manuals in the order given, each with its state."""
    sops = [s for s in sources if s.kind in KINDS]
    newest: dict[str, SourceView] = {}
    for s in sops:
        key = title_of(s).casefold()
        kept = newest.get(key)
        if kept is None or (_start(s.version_date), s.created_at) > (
            _start(kept.version_date),
            kept.created_at,
        ):
            newest[key] = s
    out = []
    for s in sops:
        if s.owner_role_id and s.owner_role_id in roles:
            owner, status = roles[s.owner_role_id], "role"
        elif s.owner.strip():
            owner, status = s.owner.strip(), ("other" if s.owner_checked else "check")
        else:
            owner, status = "", "none"
        updater = roles.get(s.updated_by_role_id or "", "") or s.updated_by_other.strip()
        out.append(
            Entry(
                source_id=s.id,
                title=title_of(s),
                kind=s.kind,
                owner=owner,
                owner_status=status,
                updated_by=updater,
                version_date=s.version_date,
                last_reviewed=s.last_reviewed,
                review_due=s.review_due,
                controlled=s.controlled_copy
                if (s.controlled_copy_set or s.controlled_copy)
                else None,
                overdue=bool(s.review_due) and _end(s.review_due) < today,
                older=newest[title_of(s).casefold()].id != s.id,
            )
        )
    return out


def counts(found: Sequence[Entry]) -> Counts:
    current = [e for e in found if not e.older]
    return Counts(
        sops=len(current),
        without_owner=sum(1 for e in current if e.owner_status == "none"),
        without_updater=sum(1 for e in current if not e.updated_by),
        overdue=sum(1 for e in current if e.overdue),
        uncontrolled=sum(1 for e in current if e.controlled is False),
    )


DOCUMENT_KINDS = frozenset({SourceKind.SOP.value, SourceKind.MANUAL.value})


def uncited_steps(steps: Sequence[GraphElement]) -> list[str]:
    """DECISIONS 113: the steps no SOP or manual governs: none of their checked, non-silent
    passages comes from one. Worked out from the map; Eric types nothing."""
    return [
        e.id
        for e in steps
        if not any(
            ev.verified and ev.stance != "silent" and ev.source_kind in DOCUMENT_KINDS
            for ev in e.evidence
        )
    ]
