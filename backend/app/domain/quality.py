"""The publish quality card (PRD §7.2): ten checks, all hard ones green before a version can be
published. Stored with the version and printed at the top of every export."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.graph import Graph, LintReport, Out

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
