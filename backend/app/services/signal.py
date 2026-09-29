"""Signal strength (P12, Eric's decision 2026-09-29): how much independent evidence a map rests
on, worked out from the kinds of its sources. An interview is always there (a draft needs one);
a written procedure (SOP or manual) lets steps be corroborated or contested, other documents
add less. Advisory only: it never blocks drafting or publishing.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import SourceKind
from app.domain.models import SignalStrength

PROCEDURES = {SourceKind.SOP.value, SourceKind.MANUAL.value}
TRANSCRIPT = SourceKind.INTERVIEW_TRANSCRIPT.value

STRONG = SignalStrength(
    level="strong",
    label="Strong",
    score=3,
    detail="Built from interviews and a written procedure (SOP or manual): steps can be "
    "corroborated or contested.",
)
MODERATE = SignalStrength(
    level="moderate",
    label="Moderate",
    score=2,
    detail="Built from interviews and supporting documents, but no SOP or manual: steps can't "
    "be checked against a written procedure.",
)
LIMITED = SignalStrength(
    level="limited",
    label="Limited",
    score=1,
    detail="Built from interviews only. Every step is 'practiced only': confirm it with a "
    "document or another SME before relying on it.",
)
QUALITY_WARNING = (
    "Signal strength: Limited. Built from interviews only; confirm the steps with a document or "
    "another SME before relying on them."
)


def signal_strength(kinds: Iterable[str]) -> SignalStrength | None:
    """The signal of a map drafted from sources of these kinds; None without an interview."""
    present = set(kinds)
    if TRANSCRIPT not in present:
        return None
    if present & PROCEDURES:
        return STRONG
    if present - {TRANSCRIPT}:
        return MODERATE
    return LIMITED
