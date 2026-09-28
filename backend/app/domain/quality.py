"""The publish quality card (PRD §7.2): ten checks, all hard ones green before a version can be
published. Stored with the version and printed at the top of every export."""

from __future__ import annotations

from typing import Literal

from app.domain.graph import Out

CheckStatus = Literal["pass", "fail", "warning"]


class QualityCheck(Out):
    id: str  # Q1 … Q10
    name: str
    status: CheckStatus
    hard: bool
    detail: str


class QualityCard(Out):
    checks: list[QualityCheck]
    #: Extra warnings listed beneath the card (steps without time or KPI, AI flags outside 3-7 ...).
    warnings: list[str]
    #: True when every hard check passes (Q10 is only a warning).
    all_green: bool
