"""Shared codes (PRD §3.5 `shared_codes`; DECISIONS 96): the only database access.

A step is shown as S-01 and an intent statement as I1. The code belongs to the engagement and
to the step's stable key (or the statement's ID), is given once and is never deleted, so it
survives a refresh, a reopened version and a republish, and is never given to anything else.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.read_memo import MEMO, remembered
from app.repositories.tables import SharedCode

STEP = "step"
INTENT = "intent"


def step_code(number: int) -> str:
    return f"S-{number:02d}"


def intent_code(number: int) -> str:
    return f"I{number}"


FORMATS: dict[str, Callable[[int], str]] = {STEP: step_code, INTENT: intent_code}


def _number(code: str) -> int:
    digits = "".join(ch for ch in code if ch.isdigit())
    return int(digits) if digits else 0


@remembered
def for_engagement(session: Session, engagement_id: str, kind: str) -> dict[str, str]:
    """ref key -> code, for every code ever given in the engagement."""
    rows = session.scalars(
        select(SharedCode).where(SharedCode.engagement_id == engagement_id, SharedCode.kind == kind)
    )
    return {r.ref_key: r.code for r in rows}


def ensure(
    session: Session, engagement_id: str, kind: str, ref_keys: Sequence[str]
) -> dict[str, str]:
    """Every code of the engagement, after giving the next numbers, in the order given, to the
    keys that have none. Inside a read-only request nothing is given: the codes already there."""
    known = for_engagement(session, engagement_id, kind)
    missing = [k for k in dict.fromkeys(ref_keys) if k not in known]
    if not missing or MEMO in session.info:
        return known
    number = max((_number(c) for c in known.values()), default=0)
    for key in missing:
        number += 1
        code = FORMATS[kind](number)
        session.add(SharedCode(engagement_id=engagement_id, kind=kind, ref_key=key, code=code))
        known[key] = code
    session.flush()
    return known
