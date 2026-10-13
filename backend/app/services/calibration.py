"""Calibration mechanics (PRD §3.7 S3, §3.8 G7): deterministic, no AI, no database.

- `assign_source_state`: the source state of one element from the stances of its sources.
- `jd_accountability_test`: do the job descriptions, documents and the interview name the same
  Accountable role for a decision or approval?
- `derive_confidence`: the G7 confidence value with the terms it is made of.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import Provenance, SourceKind, SourceState, Stance, VerifierVerdict
from app.domain.models import (
    AccountabilityTest,
    AccountableFact,
    Confidence,
    ConfidenceTerm,
    StanceFact,
)

INTERVIEW = {SourceKind.INTERVIEW_TRANSCRIPT.value}
# Written accounts of the process. Executed artefacts also count as documents for agreement and
# have their own rule (trace_contradicted). Job descriptions count only for RACI and decision
# rights (constraint 4). Working spreadsheets and email threads are artefacts too (criterion 92,
# R11): traces of work as done.
DOCUMENTS = {SourceKind.SOP.value, SourceKind.MANUAL.value, SourceKind.OTHER.value}
ARTEFACTS = {
    SourceKind.EXECUTED_ARTEFACT.value,
    SourceKind.WORKING_SPREADSHEET.value,
    SourceKind.EMAIL_THREAD.value,
}
JOB_DESCRIPTIONS = {SourceKind.JOB_DESCRIPTION.value}
COUNTED = INTERVIEW | DOCUMENTS | ARTEFACTS

BASE = {Provenance.OBSERVED.value: 0.60, Provenance.INFERRED.value: 0.40}
PER_EXTRA_SOURCE = 0.15
MAX_EXTRA_SOURCES = 2  # +0.30 at most
VERIFIER_DELTA = {VerifierVerdict.SUPPORTED.value: 0.10, VerifierVerdict.PARTIAL.value: -0.20}
CONTESTED_CAP = 0.60
LOW_CONFIDENCE = 0.50  # below this, a validation question (G7)

SUPPORTS, CONTRADICTS, SILENT = Stance.SUPPORTS.value, Stance.CONTRADICTS.value, Stance.SILENT.value


def _addressing(stances: Iterable[StanceFact], kinds: set[str]) -> list[str]:
    return [s.stance for s in stances if s.source_kind in kinds and s.stance != SILENT]


def assign_source_state(stances: Iterable[StanceFact], provenance: str) -> str:
    """Source state of one element (PRD §3.7). Silence is never contradiction (constraint 4).

    Order: R elements are not assessed; then trace_contradicted, contested, corroborated,
    practiced_only, documented_only; an element no counted source addresses is not assessed.
    """
    if provenance == Provenance.RECOMMENDED.value:
        return SourceState.NOT_ASSESSED.value
    stances = [s for s in stances if s.source_kind in COUNTED]
    interview = _addressing(stances, INTERVIEW)
    documents = _addressing(stances, DOCUMENTS | ARTEFACTS)
    artefacts = _addressing(stances, ARTEFACTS)
    interview_or_docs_support = SUPPORTS in interview or SUPPORTS in _addressing(stances, DOCUMENTS)

    if CONTRADICTS in artefacts and interview_or_docs_support:
        return SourceState.TRACE_CONTRADICTED.value
    if interview and documents and any(d != i for i in interview for d in documents):
        return SourceState.CONTESTED.value
    if SUPPORTS in interview and SUPPORTS in documents:
        return SourceState.CORROBORATED.value
    if SUPPORTS in interview and not documents:
        return SourceState.PRACTICED_ONLY.value
    if SUPPORTS in documents and not interview:
        return SourceState.DOCUMENTED_ONLY.value
    return SourceState.NOT_ASSESSED.value


def supporting_sources(stances: Iterable[StanceFact]) -> int:
    """Independent sources (distinct, JD excluded) that support an element, for G7."""
    return len({s.source_id for s in stances if s.source_kind in COUNTED and s.stance == SUPPORTS})


def _key(role: str) -> str:
    return " ".join(role.split()).casefold()


def jd_accountability_test(facts: Iterable[AccountableFact]) -> AccountabilityTest:
    """Compare the Accountable role per job description, document and interview (PRD §3.7).

    Two or more different roles → contested (divergence `ownership`, `raci.contested` on each
    competing A). A source that names no Accountable role is silent and changes nothing.
    """
    roles: list[str] = []
    by_key: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    for fact in facts:
        if not fact.role.strip() or fact.source_kind not in COUNTED | JOB_DESCRIPTIONS:
            continue
        key = _key(fact.role)
        if key not in by_key:
            by_key[key] = " ".join(fact.role.split())
            roles.append(by_key[key])
        listed = sources.setdefault(by_key[key], [])
        if fact.source_id not in listed:
            listed.append(fact.source_id)
    return AccountabilityTest(contested=len(roles) > 1, roles=roles, sources_by_role=sources)


def _cents(value: float) -> int:
    return round(value * 100)


def derive_confidence(
    provenance: str, supporting: int, verifier: str, contested: bool
) -> Confidence:
    """G7: start 0.60 (O) or 0.40 (I); +0.15 per additional supporting source (max +0.30);
    +0.10 verifier supported, -0.20 partial; capped at 0.60 while contested; clamped to 0 to 1.

    Every term is a whole number of hundredths, so the listed terms sum exactly to the value.
    """
    if provenance not in BASE:
        raise ValueError(f"confidence is computed for O and I elements only, not {provenance!r}")
    label = "Observed (O)" if provenance == Provenance.OBSERVED.value else "Inferred (I)"
    terms = [(label, _cents(BASE[provenance]))]
    extra = min(max(supporting - 1, 0), MAX_EXTRA_SOURCES)
    if extra:
        what = (
            "1 more independent source supports"
            if extra == 1
            else (f"{extra} more independent sources support")
        )
        terms.append((what, extra * _cents(PER_EXTRA_SOURCE)))
    if verifier in VERIFIER_DELTA:
        terms.append((f"Independent verifier: {verifier}", _cents(VERIFIER_DELTA[verifier])))
    elif verifier == VerifierVerdict.NOT_RUN.value:
        terms.append(("Independent verifier: not run", 0))
    total = sum(delta for _, delta in terms)
    if contested and total > _cents(CONTESTED_CAP):
        terms.append(("Capped at 0.60 while contested", _cents(CONTESTED_CAP) - total))
        total = _cents(CONTESTED_CAP)
    if total > 100:
        terms.append(("Capped at 1.00", 100 - total))
        total = 100
    if total < 0:
        terms.append(("Raised to 0.00 (the lowest value)", -total))
        total = 0
    return Confidence(
        value=total / 100,
        breakdown=[ConfidenceTerm(label=label, delta=delta / 100) for label, delta in terms],
    )
