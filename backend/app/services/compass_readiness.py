"""Ready to send to the Capability Compass (DECISIONS 113): for one version, what each question of
Eric's executive committee still lacks before the return file is downloaded. Fixed rules, no AI;
it never blocks the download (a figure that can't be counted is simply left out of the file).

Items: who decides on paper (decisions and approvals), systems of record and work and waiting
times (steps), how data moves (handoffs), SOP owners and updaters, steps citing no SOP or manual
(shown, not something to fill), the process owner, and the differences from a reference unit not
classed yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.graph import GraphElement
from app.domain.leadership import ProcessSummary
from app.services.sop_register import Entry

DECIDING = frozenset({"decision", "approval"})


@dataclass(frozen=True, slots=True)
class Item:
    key: str
    text: str
    done: int | None  # None: a yes/no item or one to read, not to fill
    total: int | None
    complete: bool | None  # None: shown for information
    screen: str  # where it is recorded (a nav key)


@dataclass(frozen=True, slots=True)
class Difference:
    reference: str  # the reference unit's name
    open: int


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _of(key: str, what: str, done: int, total: int, units: tuple[str, str], screen: str) -> Item:
    return Item(key, f"{what}: recorded on {done} of {_count(total, *units)}", done, total,
                done == total, screen)  # fmt: skip


def items(
    steps: Sequence[GraphElement],
    summary: ProcessSummary,
    sops: Sequence[Entry],
    uncited: int,
    differences: Sequence[Difference],
) -> list[Item]:
    deciding = [e for e in steps if e.kind in DECIDING]
    steps_words = ("step", "steps")
    on_paper = sum(1 for e in deciding if e.paper_decider is not None)
    systems = sum(1 for e in steps if e.system_of_record is not None)
    out: list[Item | None] = [
        _of("on_paper", "Decider named in the documents", on_paper, len(deciding),
            ("decision or approval", "decisions and approvals"), "review") if deciding else None,
        _of("systems", "System of record", systems, len(steps), steps_words, "review"),
        _of("data_moves", "How data moves", summary.handoffs_known, summary.handoffs,
            ("handoff", "handoffs"), "review") if summary.handoffs else None,
        _of("times", "Work and waiting times", summary.timed_steps, summary.steps, steps_words,
            "review"),
    ]  # fmt: skip
    current = [e for e in sops if not e.older]
    if current:
        both = sum(1 for e in current if e.owner_status != "none" and e.updated_by)
        check = sum(1 for e in current if e.owner_status == "check")
        text = (f"SOP owners and updaters: both recorded for {both} of "
                f"{_count(len(current), 'SOP or manual', 'SOPs and manuals')}")  # fmt: skip
        if check:
            text += f"; {_count(check, 'owner', 'owners')} to check"
        out.append(Item("sop_owners", text, both, len(current), both == len(current) and not check,
                        "sources"))  # fmt: skip
    if steps:
        out.append(Item("uncited", f"Steps citing no SOP or manual: {uncited} of {len(steps)}",
                        None, None, None, "sources"))  # fmt: skip
    owner = summary.process_owner
    out.append(Item("process_owner", f"Process owner: {owner or 'not named'}", None, None,
                    bool(owner), "setup"))  # fmt: skip
    for d in differences:
        out.append(Item("differences",
                        f"Differences from {d.reference}: {d.open} not classed or kept yet",
                        None, None, d.open == 0, "compare"))  # fmt: skip
    return [i for i in out if i is not None]
