"""The publish quality card (PRD §7.2): Q1-Q9 hard checks, all green before a version can be
published, and the warnings Q10-Q12 (Q12 only with system records). Stored with the version and
printed at the top of every export."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.graph import Graph, LintReport, Out

CheckStatus = Literal["pass", "fail", "warning"]


class QualityCheck(Out):
    id: str  # Q1 … Q12
    name: str
    status: CheckStatus
    hard: bool
    detail: str


class QualityCard(Out):
    checks: list[QualityCheck]
    #: Extra warnings listed beneath the card (steps without time or KPI, AI flags outside 3-7 ...).
    warnings: list[str]
    #: True when every hard check passes (Q10-Q12 are only warnings).
    all_green: bool


class QualityInput(BaseModel):
    """What the quality card is worked out from (`services/quality.build_quality_card`)."""

    graph: Graph
    lint: LintReport
    pending_merges: int
    open_image_suggestions: int
    #: Claims behind the map's steps that are not verified (should always be 0).
    unverified_claims: int
    #: The rendered exports, by format: md, json, csv, html.
    exports: dict[str, str]
    #: Names on the redaction list (the owner-only list; never shown by the card).
    hidden_terms: list[str]
    #: Kinds of the sources the version was drafted from (its signal strength, P12).
    source_kinds: list[str] = []
    #: Q12 (v1.11): imported system-log activities neither aligned nor marked hidden work; None
    #: when the engagement uses no system records (the check is then left off the card).
    unaligned_activities: int | None = None
