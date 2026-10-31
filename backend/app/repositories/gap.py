"""Gap analysis repository (PRD §3.5 gap_analyses, gap_findings; §3.11): analyses of a version and
their findings. Nothing here touches the map."""

from __future__ import annotations

from sqlalchemy import delete, literal_column, select
from sqlalchemy.orm import Session

from app.domain.gap import (
    GapAnalysisRecord,
    GapEvidence,
    GapSourceView,
    NewExternalSource,
    NewGapFinding,
    StoredGapFinding,
)
from app.repositories.read_memo import remembered
from app.repositories.tables import (
    Element,
    ExternalCitation,
    ExternalSource,
    GapAnalysis,
    GapFinding,
    MapVersion,
    now_iso,
)


def _record(row: GapAnalysis) -> GapAnalysisRecord:
    return GapAnalysisRecord.model_validate(row, from_attributes=True)


def _finding(row: GapFinding) -> StoredGapFinding:
    return StoredGapFinding(
        id=row.id,
        section=row.section,
        finding_type=row.finding_type,
        title=row.title,
        text=row.text,
        element_ids=list(row.element_ids or []),
        evidence=[GapEvidence.model_validate(e) for e in row.evidence or []],
        basis=row.basis,
        provenance=row.provenance,
        severity=row.severity,
        evidence_strength=row.evidence_strength,
        comparison=row.comparison,
        verification_status=row.verification_status,
        rejection_guardrail=row.rejection_guardrail,
        rejection_reason=row.rejection_reason,
        verifier_verdict=row.verifier_verdict,
        question=row.question,
        notes=list(row.notes or []),
        disposition=row.disposition,
        disposition_note=row.disposition_note,
        created_item_ref=row.created_item_ref,
        gap_class=row.gap_class,
        stated_reason=row.stated_reason or "",
        cause_type=row.cause_type,
    )


def create(
    session: Session,
    *,
    version_id: str,
    mode: str,
    status: str,
    brief: dict[str, object] | None = None,
    brief_scan: dict[str, object] | None = None,
) -> GapAnalysisRecord:
    row = GapAnalysis(
        version_id=version_id, mode=mode, status=status, brief=brief, brief_scan=brief_scan
    )
    session.add(row)
    session.flush()
    return _record(row)


def get(session: Session, analysis_id: str) -> GapAnalysisRecord | None:
    row = session.get(GapAnalysis, analysis_id)
    return _record(row) if row else None


@remembered
def for_version(session: Session, version_id: str) -> list[GapAnalysisRecord]:
    """Newest first."""
    rows = session.scalars(
        select(GapAnalysis)
        .where(GapAnalysis.version_id == version_id)
        .order_by(GapAnalysis.created_at.desc(), GapAnalysis.id.desc())
    )
    return [_record(r) for r in rows]


def set_status(
    session: Session, analysis_id: str, status: str, *, model: str | None = None
) -> None:
    row = session.get(GapAnalysis, analysis_id)
    if row is None:
        return
    row.status = status
    if model is not None:
        row.model = model
    if status in {"draft_report", "failed"}:
        row.completed_at = now_iso()
    elif status == "queued":
        row.completed_at = None
    session.flush()


def replace_findings(session: Session, analysis_id: str, findings: list[NewGapFinding]) -> None:
    """The analysis's findings, replacing any from an earlier, interrupted run."""
    session.execute(delete(GapFinding).where(GapFinding.analysis_id == analysis_id))
    for f in findings:
        data = f.model_dump()
        data["evidence"] = [e.model_dump() for e in f.evidence]
        session.add(GapFinding(analysis_id=analysis_id, **data))
    session.flush()


def findings(session: Session, analysis_id: str) -> list[StoredGapFinding]:
    """In the order they were stored."""
    rows = session.scalars(
        select(GapFinding)
        .where(GapFinding.analysis_id == analysis_id)
        .order_by(literal_column("gap_findings.rowid"))  # insertion order
    )
    return [_finding(r) for r in rows]


def set_brief(
    session: Session,
    analysis_id: str,
    *,
    brief: dict[str, object],
    confirmed: bool,
    scan: dict[str, object],
) -> GapAnalysisRecord:
    row = session.get(GapAnalysis, analysis_id)
    assert row is not None
    row.brief = brief
    row.brief_confirmed = confirmed
    row.brief_scan = scan
    row.settings = {
        k: brief.get(k)
        for k in ("max_searches", "allowed_domains", "blocked_domains", "recency_years")
    }
    session.flush()
    return _record(row)


def set_outcome(session: Session, analysis_id: str, *, search_count: int, notes: list[str]) -> None:
    row = session.get(GapAnalysis, analysis_id)
    if row is None:
        return
    row.search_count = search_count
    row.notes = notes
    session.flush()


def replace_sources(
    session: Session,
    analysis_id: str,
    sources: list[NewExternalSource],
    citations: list[tuple[str, str, str]],
) -> None:
    """Every page the research returned or cited, and each citation (ID, URL, cited text)."""
    session.execute(delete(ExternalCitation).where(ExternalCitation.analysis_id == analysis_id))
    session.execute(delete(ExternalSource).where(ExternalSource.analysis_id == analysis_id))
    ids: dict[str, str] = {}
    for source in sources:
        row = ExternalSource(analysis_id=analysis_id, **source.model_dump())
        session.add(row)
        session.flush()
        ids[source.url] = row.id
    for ref, url, cited_text in citations:
        session.add(
            ExternalCitation(
                analysis_id=analysis_id,
                source_id=ids[url],
                citation_ref=ref,
                cited_text=cited_text,
            )
        )
    session.flush()


def sources(session: Session, analysis_id: str) -> list[GapSourceView]:
    """In the order the research returned them."""
    rows = session.scalars(
        select(ExternalSource)
        .where(ExternalSource.analysis_id == analysis_id)
        .order_by(literal_column("external_sources.rowid"))
    )
    return [
        GapSourceView(
            id=r.id,
            url=r.url,
            title=r.title,
            domain=r.domain,
            page_age=r.page_age,
            tier=r.tier,
            returned_in_results=r.returned_in_results,
        )
        for r in rows
    ]


def finding(session: Session, finding_id: str) -> tuple[str, StoredGapFinding] | None:
    """(analysis ID, finding)."""
    row = session.get(GapFinding, finding_id)
    return (row.analysis_id, _finding(row)) if row else None


def set_disposition(
    session: Session,
    finding_id: str,
    disposition: str,
    note: str,
    created_item_ref: str,
    gap_class: str | None = None,
) -> StoredGapFinding:
    row = session.get(GapFinding, finding_id)
    assert row is not None
    if gap_class is not None:
        row.gap_class = gap_class
    row.disposition = disposition
    row.disposition_note = note
    row.created_item_ref = created_item_ref
    session.flush()
    return _finding(row)


def finalise(session: Session, analysis_id: str) -> None:
    row = session.get(GapAnalysis, analysis_id)
    if row is None:
        return
    row.status = "finalised"
    row.finalised_at = now_iso()
    session.flush()


def step_findings(
    session: Session, engagement_id: str, stable_key: str
) -> list[tuple[GapAnalysisRecord, StoredGapFinding]]:
    """Kept findings of every analysis in the engagement that name a step with this key, newest
    analysis first."""
    ids = set(
        session.scalars(
            select(Element.id)
            .join(MapVersion, MapVersion.id == Element.version_id)
            .where(MapVersion.engagement_id == engagement_id, Element.stable_key == stable_key)
        )
    )
    rows = session.execute(
        select(GapAnalysis, GapFinding)
        .join(GapFinding, GapFinding.analysis_id == GapAnalysis.id)
        .join(MapVersion, MapVersion.id == GapAnalysis.version_id)
        .where(MapVersion.engagement_id == engagement_id)
        .where(GapFinding.verification_status != "rejected")
        .order_by(
            GapAnalysis.created_at.desc(),
            GapAnalysis.id.desc(),
            literal_column("gap_findings.rowid"),
        )
    )
    return [
        (_record(analysis), _finding(found))
        for analysis, found in rows
        if ids & set(found.element_ids or [])
    ]
