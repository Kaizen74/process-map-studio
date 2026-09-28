"""Gap analysis (PRD §3.11, API_CONTRACT → Gap analysis; phase P10): start, run and report.

Advisory and on demand (constraint 22): an analysis runs only when Eric starts it, and nothing
here changes the map. Analysis A (documents vs practice) runs as a background job of type
`gap_internal` whose target is the analysis.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions.draft import now_iso
from app.config import AppConfig
from app.db import session_scope
from app.domain.gap import (
    GapAnalysisRecord,
    GapAnalysisView,
    GapCounts,
    GapElementRef,
    GapFindingView,
    GapReport,
    GapStarted,
    GapUsage,
    StoredGapFinding,
)
from app.domain.models import JobStage
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import ga_internal
from app.pipeline.context import ai_context
from app.repositories import ai_calls
from app.repositories import elements as map_repo
from app.repositories import gap as repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

INTERNAL_JOB = "gap_internal"
GAP_JOBS = (INTERNAL_JOB,)
VERSION_MISSING = "That version doesn't exist."
ANALYSIS_MISSING = "That gap analysis doesn't exist."
BUSY = "A gap analysis is already running for this version."
UNEXPECTED = (
    "Something went wrong while running the gap analysis. The map wasn't changed. Try again, "
    "or use Copy details to report it."
)
INTERNAL_STAGES = (
    ("collect", "Finding where the sources differ"),
    ("synthesise", "Explaining the differences"),
    ("check", "Checking every quote against your documents"),
    ("verify", "Independent verification"),
    ("report", "Writing the report"),
)
SECTION_ORDER = {"fact": 0, "interpretation": 1, "recommendation": 2}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _stages() -> list[JobStage]:
    return [JobStage(id=sid, name=name, status="waiting") for sid, name in INTERNAL_STAGES]


# --- Starting ----------------------------------------------------------------------------------


def start_internal(sessions: Sessions, version_id: str, enqueue: Enqueue) -> Result[GapStarted]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None or version.state == "building":
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        for earlier in repo.for_version(session, version_id):
            if earlier.status in {"queued", "running"}:
                return Err(ErrorKind.CONFLICT, BUSY, {"analysis_id": earlier.id})
        analysis = repo.create(session, version_id=version_id, mode="internal", status="queued")
        job = jobs_repo.create(
            session,
            engagement_id=version.engagement_id,
            job_type=INTERNAL_JOB,
            target_id=analysis.id,
            stages=_stages(),
        )
    enqueue(job.id)
    return Ok(GapStarted(analysis_id=analysis.id, job_id=job.id))


# --- Running -----------------------------------------------------------------------------------


class _Progress:
    def __init__(self, sessions: Sessions, job_id: str) -> None:
        self.sessions = sessions
        self.job_id = job_id
        self.stages = _stages()

    def _save(self, **fields: object) -> None:
        with session_scope(self.sessions) as session:
            jobs_repo.update(session, self.job_id, stages=self.stages, **fields)  # type: ignore[arg-type]

    def mark(self, sid: str, status: str, share: float | None = None) -> None:
        stage = next(s for s in self.stages if s.id == sid)
        stage.status = status
        if status == "running":
            stage.started_at = now_iso()
            self._save(stage=stage.name)
            return
        stage.started_at = stage.started_at or now_iso()
        stage.finished_at = now_iso()
        if share is None:
            self._save()
        else:
            self._save(progress=share)

    def fail(self) -> None:
        for stage in self.stages:
            if stage.status == "running":
                stage.status = "failed"
                stage.finished_at = now_iso()
        self._save()


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def run_internal(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """Run one Analysis A job. On failure the analysis is `failed` with no findings."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        analysis = repo.get(session, job.target_id or "") if job else None
    if job is None or analysis is None:
        return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
    progress = _Progress(sessions, job_id)

    def failed(err: Err) -> Err:
        progress.fail()
        with session_scope(sessions) as session:
            repo.replace_findings(session, analysis.id, [])
            repo.set_status(session, analysis.id, "failed")
        return err

    with session_scope(sessions) as session:
        repo.set_status(session, analysis.id, "running")
    progress.mark("collect", "running")
    match ai_context(config):
        case Err() as err:
            return failed(err)
        case Ok(value=ctx):
            pass
    try:
        with session_scope(sessions) as session:
            dset = ga_internal.divergence_set(session, analysis.version_id)
        if dset is None:
            return failed(Err(ErrorKind.NOT_FOUND, VERSION_MISSING))
        progress.mark("collect", "done", 0.1)

        progress.mark("synthesise", "running")
        match ga_internal.synthesise(sessions, ctx, dset, job_id):
            case Err() as err:
                return failed(err)
            case Ok(value=output):
                pass
        progress.mark("synthesise", "done", 0.6)

        progress.mark("check", "running")
        checked = [ga_internal.check(dset, f) for f in output.findings]
        progress.mark("check", "done", 0.65)

        if ctx.verifier_enabled:
            progress.mark("verify", "running")
            if isinstance(outcome := ga_internal.verify(sessions, ctx, dset, checked, job_id), Err):
                return failed(outcome)
            progress.mark("verify", "done", 0.9)
        else:
            progress.mark("verify", "skipped", 0.9)

        progress.mark("report", "running")
        findings = ga_internal.report(dset, checked, output.unknowns)
        with session_scope(sessions) as session:
            repo.replace_findings(session, analysis.id, findings)
            repo.set_status(session, analysis.id, "draft_report", model=ctx.model)
        progress.mark("report", "done", 1.0)
    except Exception:
        failed(Err(ErrorKind.IO, UNEXPECTED))
        raise
    kept = [f for f in findings if f.verification_status != "rejected" and not f.question]
    questions = [f for f in findings if f.question]
    rejected = len(findings) - len(kept) - len(questions)
    return Ok(
        f"The documents-vs-practice report is ready: {_plural(len(kept), 'finding')}, "
        f"{_plural(len(questions), 'question')} for your SMEs, "
        f"{_plural(rejected, 'rejected finding')}."
    )


# --- Reporting ---------------------------------------------------------------------------------


def _counts(findings: list[StoredGapFinding]) -> GapCounts:
    kept = [f for f in findings if f.verification_status != "rejected"]
    return GapCounts(
        kept=len([f for f in kept if not f.question]),
        rejected=len(findings) - len(kept),
        open=len([f for f in kept if f.disposition == "open"]),
        needs_check=len([f for f in kept if f.verifier_verdict == "partial"]),
    )


def _view(session: Session, analysis: GapAnalysisRecord) -> GapAnalysisView:
    version = versions_repo.get(session, analysis.version_id)
    job = jobs_repo.for_target(session, analysis.id)
    return GapAnalysisView(
        id=analysis.id,
        version_id=analysis.version_id,
        version_label=version.label if version else "",
        mode=analysis.mode,
        status=analysis.status,
        job_id=job.id if job else None,
        error=job.error if job and analysis.status == "failed" else "",
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        finalised_at=analysis.finalised_at,
        counts=_counts(repo.findings(session, analysis.id)),
    )


def list_analyses(sessions: Sessions, version_id: str) -> Result[list[GapAnalysisView]]:
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        return Ok([_view(session, a) for a in repo.for_version(session, version_id)])


def _finding_view(f: StoredGapFinding, labels: dict[str, str]) -> GapFindingView:
    return GapFindingView(
        **f.model_dump(exclude={"evidence"}),
        evidence=f.evidence,
        elements=[GapElementRef(id=e, label=labels.get(e, "")) for e in f.element_ids],
        needs_check=f.verifier_verdict == "partial",
    )


def get_report(sessions: Sessions, analysis_id: str) -> Result[GapReport]:
    with session_scope(sessions) as session:
        analysis = repo.get(session, analysis_id)
        if analysis is None:
            return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
        view = _view(session, analysis)
        version = versions_repo.get(session, analysis.version_id)
        terms = redaction.name_replacements(session, version.engagement_id) if version else []
        labels = {
            e.id: redaction.hide(e.label, terms)
            for e in map_repo.elements(session, analysis.version_id)
        }
        stored = repo.findings(session, analysis_id)
        job = jobs_repo.for_target(session, analysis_id)
        usage = ai_calls.usage_for_job(session, job.id) if job else None
    views = [_finding_view(f, labels) for f in stored]
    order = {f.id: n for n, f in enumerate(stored)}

    def rank(f: GapFindingView) -> tuple[int, int, int]:
        return (
            SECTION_ORDER.get(f.section, 3),
            SEVERITY_ORDER.get(f.severity or "", 3),
            order[f.id],
        )

    kept = [f for f in views if f.verification_status != "rejected"]
    return Ok(
        GapReport(
            analysis=view,
            findings=sorted([f for f in kept if not f.question], key=rank),
            rejected=[f for f in views if f.verification_status == "rejected"],
            sources=[],
            questions=[f for f in kept if f.question],
            usage=GapUsage(**usage) if usage else None,
            search_count=analysis.search_count,
        )
    )
