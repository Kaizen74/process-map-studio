"""The process at a glance (PRD §3.20; DECISIONS 110): one version's steps, decisions, approvals,
handoffs between roles, rework loops, work and waiting time, and the data lens (systems of
record, handoffs by hand, steps off-system or with no record). Pure and deterministic; the
leadership view and the Capability Compass return file read the same figures from here.

- Steps, handoffs and rework loops are counted exactly as the leadership view counts them.
- A figure that can't be counted is None: times when no step has one; systems until a step has a
  system of record; handoffs by hand until a handoff has how its data moves; D6 and D11 while the
  Reality views are off (`off_system`/`no_record` None).
"""

from __future__ import annotations

from collections.abc import Set

from app.domain.enums import DataMove, ElementKind
from app.domain.graph import Graph
from app.domain.leadership import ProcessSummary, SummaryLinks
from app.services.leadership import LOOPS, steps_of

MANUAL = frozenset(
    {DataMove.RE_KEYED.value, DataMove.EMAIL_SPREADSHEET.value, DataMove.PAPER.value,
     DataMove.VERBAL.value}
)  # fmt: skip


def _system_key(status: str, role_id: str | None, other: str) -> str | None:
    if status == "system" and role_id:
        return f"role:{role_id}"
    if status == "other" and other.strip():
        return "other:" + " ".join(other.casefold().split())
    return None


def summarise(
    graph: Graph,
    process_owner: str,
    off_system: Set[str] | None = None,
    no_record: Set[str] | None = None,
    steps_differing: int | None = None,
) -> ProcessSummary:
    steps = steps_of(graph)
    by_id = {e.id: e for e in steps}
    handoffs = [
        x for x in graph.edges
        if x.from_ in by_id and x.to in by_id
        and by_id[x.from_].lane_role_id != by_id[x.to].lane_role_id
    ]  # fmt: skip
    loops = [x.from_ for x in graph.edges if x.kind in LOOPS and x.from_ in by_id and x.to in by_id]
    timed = [e for e in steps if e.time.work_min is not None or e.time.wait_min is not None]
    worked = [e.time.work_min for e in steps if e.time.work_min is not None]
    waited = [e.time.wait_min for e in steps if e.time.wait_min is not None]
    recorded = [e for e in steps if e.system_of_record is not None]
    systems: dict[str, str] = {}
    for e in recorded:
        sor = e.system_of_record
        key = _system_key(sor.status, sor.role_id, sor.other) if sor else None
        if key:
            systems[e.id] = key
    known = [x for x in handoffs if x.data_move]
    manual = [x for x in known if x.data_move in MANUAL]
    off = [e.id for e in steps if off_system is not None and e.id in off_system]
    none = [e.id for e in steps if no_record is not None and e.id in no_record]
    return ProcessSummary(
        process_owner=process_owner,
        steps=len(steps),
        decisions=sum(1 for e in steps if e.kind == ElementKind.DECISION.value),
        approvals=sum(1 for e in steps if e.kind == ElementKind.APPROVAL.value),
        handoffs=len(handoffs),
        roles=len({e.lane_role_id for e in steps if e.lane_role_id}),
        rework_loops=len(loops),
        work_min=round(sum(worked)) if worked else None,
        wait_min=round(sum(waited)) if waited else None,
        timed_steps=len(timed),
        systems=len(set(systems.values())) if recorded else None,
        handoffs_known=len(known),
        handoffs_manual=len(manual) if known else None,
        off_system_steps=len(off) if off_system is not None else None,
        no_record_steps=len(none) if no_record is not None else None,
        steps_differing=steps_differing,
        links=SummaryLinks(
            steps=[e.id for e in steps],
            handoffs=list(dict.fromkeys(x.from_ for x in handoffs)),
            rework_loops=list(dict.fromkeys(loops)),
            systems=list(systems),
            handoffs_manual=list(dict.fromkeys(x.from_ for x in manual)),
            off_system=off,
            no_record=none,
        ),
    )


METRICS = (
    "steps", "decisions", "approvals", "handoffs", "roles", "rework_loops", "work_min",
    "wait_min", "systems", "handoffs_manual", "off_system_steps", "no_record_steps",
    "steps_differing",
)  # fmt: skip


def metrics(summary: ProcessSummary) -> dict[str, int]:
    """The Compass's `metrics`: what could be counted, never 0 for "not known"."""
    return {k: v for k in METRICS if (v := getattr(summary, k)) is not None}
