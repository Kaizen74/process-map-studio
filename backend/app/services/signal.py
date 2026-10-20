"""Signal strength (P12, Eric's decision 2026-09-29): how much independent evidence a map rests
on, worked out from the kinds of its sources. A written procedure (SOP or manual) beside an
interview lets steps be corroborated or contested; other documents add less. A map from
interviews alone, or (Eric, 2026-10-20) from process documents alone, is Limited: it shows only
the process as done, or only as written. Advisory only: it never blocks drafting or publishing.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import SourceKind
from app.domain.models import SignalStrength

PROCEDURES = {SourceKind.SOP.value, SourceKind.MANUAL.value}
TRANSCRIPT = SourceKind.INTERVIEW_TRANSCRIPT.value
# Kinds that describe the steps of the process. A job description alone describes roles only,
# and a policy or charter states intent and is never drafted from.
PROCESS_DOCUMENTS = {
    SourceKind.SOP.value,
    SourceKind.MANUAL.value,
    SourceKind.EXECUTED_ARTEFACT.value,
    SourceKind.WORKING_SPREADSHEET.value,
    SourceKind.EMAIL_THREAD.value,
    SourceKind.OTHER.value,
}

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
DOCUMENTS_ONLY = SignalStrength(
    level="limited",
    label="Limited",
    score=1,
    detail="Built from documents only. Every step is 'documented only': it shows the process as "
    "written, not as it is done. Confirm it with an interview before relying on it.",
)
QUALITY_WARNING = (
    "Signal strength: Limited. Built from interviews only; confirm the steps with a document or "
    "another SME before relying on them."
)
DOCUMENTS_QUALITY_WARNING = (
    "Signal strength: Limited. Built from documents only; confirm with an interview how the work "
    "is actually done before relying on the steps."
)


def signal_strength(kinds: Iterable[str]) -> SignalStrength | None:
    """The signal of a map drafted from sources of these kinds; None when none describes steps
    (no interview and no process document)."""
    present = set(kinds)
    if TRANSCRIPT not in present:
        return DOCUMENTS_ONLY if present & PROCESS_DOCUMENTS else None
    if present & PROCEDURES:
        return STRONG
    if present - {TRANSCRIPT}:
        return MODERATE
    return LIMITED


def quality_warning(strength: SignalStrength) -> str | None:
    """The quality card's warning for a Limited map, which says what it was built from."""
    if strength.level != LIMITED.level:
        return None
    return DOCUMENTS_QUALITY_WARNING if strength is DOCUMENTS_ONLY else QUALITY_WARNING
