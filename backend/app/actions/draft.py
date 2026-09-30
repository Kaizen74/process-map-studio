"""Drafting (PRD §3.7 pipeline, §4 Pipeline, §5.4 Draft): start, run and report the draft job.

In phase P3 the job reads scanned pages (S0), extracts claims from every ready source (S1) and
checks each one as it arrives (G3-G5, G10). The later stages are listed as `later`. The draft
version is created when the job starts and deleted again if any stage fails, so a failed draft
leaves nothing behind but the usage of the calls it made.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import causes, redaction, refresh, run_records
from app.actions import images as images_action
from app.actions import versions as versions_action
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.actions.readiness import get_readiness
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import (
    DraftStarted,
    DraftState,
    DraftSummary,
    JobClaims,
    JobStage,
    JobView,
    RefreshChanges,
    RejectedClaim,
    RejectedClaims,
    VersionView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import (
    s0_normalise,
    s1_extract,
    s2_canonicalise,
    s3_calibrate,
    s3b_verify,
    s4_assemble,
    s5_questions,
)
from app.pipeline.context import AiContext, ai_context
from app.repositories import ai_calls, audit, claims, versions
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import jobs as jobs_repo
from app.repositories import sources as sources_repo
from app.services import parsing

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

DRAFT_JOB = "draft"
REFRESH_JOB = "refresh"
MAP_JOBS = (DRAFT_JOB, REFRESH_JOB)
BUILDING = "building"  # the state of the version a refresh is building
FIRST_LABEL = "v0.1"
STAGES = (
    ("read", "Reading the documents"),
    ("extract", "Extracting steps from each source"),
    ("check", "Checking every quote against your documents"),
    ("compare", "Comparing sources"),
    ("verify", "Independent verification"),
    ("build", "Building the map"),
    ("questions", "Writing validation questions"),
)
BUILT = {sid for sid, _ in STAGES}  # every stage runs since phase P4
# Where the progress bar stands when each part of the run is done.
READ_SHARE, EXTRACT_SHARE, COMPARE_SHARE, VERIFY_SHARE, BUILD_SHARE = 0.05, 0.55, 0.7, 0.8, 0.9

BUSY = "A draft map is already being made."
NOT_CURRENT = "Only the current draft can be refreshed."
PUBLISHED = "This process has a published map. Reopen it as a new draft on the Published screen."
HAS_STEPS = (
    "This draft has steps you've already reviewed. Refresh it from the sources on the Review "
    "screen instead."
)
VERSION_MISSING = "That version doesn't exist."
UNEXPECTED = (
    "Something went wrong while drafting the map. Nothing was saved. Try again, or use Copy "
    "details to report it."
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def initial_stages() -> list[JobStage]:
    return [
        JobStage(id=sid, name=name, status="waiting" if sid in BUILT else "later")
        for sid, name in STAGES
    ]


def next_label(earlier: str | None) -> str:
    """v0.1 for the first draft; v0.2, v0.3 … when a new draft replaces an earlier one. A draft
    reopened from a published version ("v1.1 draft") keeps its label when it is refreshed."""
    if earlier and earlier.endswith(" draft"):
        return earlier
    if earlier and earlier.startswith("v0.") and earlier[3:].isdigit():
        return f"v0.{int(earlier[3:]) + 1}"
    return FIRST_LABEL


Stage = Callable[..., Result[object]]


def _run(
    stage: Stage,
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    version_id: str,
    job_id: str,
) -> Result[object]:
    return stage(config, sessions, ctx, version_id=version_id, job_id=job_id)  # fmt: skip


def _lint(
    _config: AppConfig, sessions: Sessions, _ctx: AiContext, *, version_id: str, job_id: str
) -> Result[object]:
    """The lint rules on the assembled map; the report is stored on the version."""
    return versions_action.lint_version(sessions, version_id)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --- Starting ----------------------------------------------------------------------------------


def start_draft(
    config: AppConfig, sessions: Sessions, engagement_id: str, enqueue: Enqueue
) -> Result[DraftStarted]:
    match get_readiness(config, sessions, engagement_id):
        case Err() as err:
            return err
        case Ok(value=ready):
            pass
    if not ready.ready_to_draft:
        missing = ready.missing
        return Err(
            ErrorKind.CONFLICT, f"The draft can't start yet: {missing[0]}.", {"missing": missing}
        )
    with session_scope(sessions) as session:
        latest = _latest_map_job(session, engagement_id)
        if latest is not None and latest.status in jobs_repo.UNFINISHED:
            return Err(ErrorKind.CONFLICT, BUSY, {"job_id": latest.id})
        draft = versions.current_draft(session, engagement_id)
        if draft is not None and versions.reviewed_count(session, draft.id) > 0:
            return Err(ErrorKind.CONFLICT, HAS_STEPS, {"version_id": draft.id})
        if draft is None and versions.latest_published(session, engagement_id) is not None:
            return Err(ErrorKind.CONFLICT, PUBLISHED)
        job = jobs_repo.create(
            session,
            engagement_id=engagement_id,
            job_type=DRAFT_JOB,
            target_id=None,
            stages=initial_stages(),
        )
    enqueue(job.id)
    return Ok(DraftStarted(job_id=job.id))


def start_refresh(
    config: AppConfig, sessions: Sessions, version_id: str, enqueue: Enqueue
) -> Result[DraftStarted]:
    """Refresh draft from sources (PRD §3.5): the whole pipeline again, folded into this draft."""
    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        current = versions.current_draft(session, version.engagement_id)
        if current is None or current.id != version.id:
            return Err(ErrorKind.CONFLICT, NOT_CURRENT)
    match get_readiness(config, sessions, version.engagement_id):
        case Err() as err:
            return err
        case Ok(value=ready):
            pass
    if not ready.ready_to_draft:
        missing = ready.missing
        return Err(
            ErrorKind.CONFLICT, f"The draft can't start yet: {missing[0]}.", {"missing": missing}
        )
    with session_scope(sessions) as session:
        latest = _latest_map_job(session, version.engagement_id)
        if latest is not None and latest.status in jobs_repo.UNFINISHED:
            return Err(ErrorKind.CONFLICT, BUSY, {"job_id": latest.id})
        job = jobs_repo.create(
            session,
            engagement_id=version.engagement_id,
            job_type=REFRESH_JOB,
            target_id=version.id,
            stages=initial_stages(),
        )
    enqueue(job.id)
    return Ok(DraftStarted(job_id=job.id))


def _latest_map_job(session: Session, engagement_id: str) -> JobView | None:
    """The newest draft or refresh job of an engagement."""
    jobs = [j for t in MAP_JOBS if (j := jobs_repo.latest(session, engagement_id, t))]
    return max(jobs, key=lambda j: j.created_at, default=None)


# --- Running -----------------------------------------------------------------------------------


class _Progress:
    """Writes the job's stages, current stage name and progress as the run moves on."""

    def __init__(self, sessions: Sessions, job_id: str) -> None:
        self.sessions = sessions
        self.job_id = job_id
        self.stages = initial_stages()

    def _save(self, *, stage: str | None = None, progress: float | None = None) -> None:
        with session_scope(self.sessions) as session:
            jobs_repo.update(
                session, self.job_id, stage=stage, progress=progress, stages=self.stages
            )

    def _set(self, sid: str, **fields: object) -> JobStage:
        stage = next(s for s in self.stages if s.id == sid)
        for name, value in fields.items():
            setattr(stage, name, value)
        return stage

    def start(self, *sids: str) -> None:
        names = [self._set(sid, status="running", started_at=now_iso()).name for sid in sids]
        self._save(stage=names[0])

    def done(self, *sids: str) -> None:
        for sid in sids:
            self._set(sid, status="done", finished_at=now_iso())
        self._save()

    def progress(self, value: float) -> None:
        self._save(progress=round(min(max(value, 0.0), 1.0), 3))

    def skip(self, sid: str) -> None:
        now = now_iso()
        self._set(sid, status="skipped", started_at=now, finished_at=now)
        self._save()

    def fail(self) -> None:
        for stage in self.stages:
            if stage.status == "running":
                stage.status = "failed"
                stage.finished_at = now_iso()
        self._save()


def discard_unfinished(sessions: Sessions, job: JobView) -> None:
    """A job run again (after a restart) first removes its half-built version."""
    if job.type == DRAFT_JOB and job.target_id:
        with session_scope(sessions) as session:
            versions.delete(session, job.target_id)
    elif job.type == REFRESH_JOB and job.engagement_id:
        with session_scope(sessions) as session:
            for half in versions.building(session, job.engagement_id):
                versions.delete(session, half.id)


def run_draft(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """Run one draft job; on failure its version and everything stored for it are deleted."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
    if job is None or job.engagement_id is None:
        return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
    discard_unfinished(sessions, job)
    progress = _Progress(sessions, job_id)
    progress.start("read")

    match ai_context(config):
        case Err() as err:
            progress.fail()
            return err
        case Ok(value=ctx):
            pass
    engagement_id = job.engagement_id
    refreshing = job.type == REFRESH_JOB
    with session_scope(sessions) as session:
        earlier = versions.current_draft(session, engagement_id)
        if refreshing and (earlier is None or earlier.id != job.target_id):
            progress.fail()
            return Err(ErrorKind.CONFLICT, NOT_CURRENT)
        version = versions.create(
            session,
            engagement_id=engagement_id,
            label=next_label(earlier.label if earlier else None),
            state=BUILDING if refreshing else "draft",
        )
        if not refreshing:
            jobs_repo.update(session, job_id, target_id=version.id)
        ready = [
            s
            for s in sources_repo.list_for_engagement(session, engagement_id)
            if s.text_status == "ready"
        ]
        map_repo.add_version_sources(session, version.id, [s.id for s in ready])

    def failed(err: Err) -> Err:
        progress.fail()
        with session_scope(sessions) as session:
            versions.delete(session, version.id)
        return err

    try:
        for source in ready:
            if source.format == "pdf" and source.ocr_pages:
                match s0_normalise.read_scanned_pages(
                    config, sessions, ctx, source_id=source.id, job_id=job_id
                ):
                    case Err() as err:
                        return failed(err)
                    case Ok():
                        pass
        progress.done("read")
        progress.progress(READ_SHARE)

        progress.start("extract", "check")
        for index, source in enumerate(ready, start=1):
            match s1_extract.extract_source(
                config, sessions, ctx, version_id=version.id, source_id=source.id, job_id=job_id
            ):
                case Err() as err:
                    return failed(err)
                case Ok():
                    pass
            share = READ_SHARE + (EXTRACT_SHARE - READ_SHARE) * index / max(len(ready), 1)
            progress.progress(share)
        progress.done("extract", "check")

        # The later stages, each on everything stored so far (PRD §3.7).
        later: list[tuple[str, list[Stage], float]] = [
            ("compare", [s2_canonicalise.canonicalise, s3_calibrate.calibrate], COMPARE_SHARE),
            ("verify", [s3b_verify.verify], VERIFY_SHARE),
            ("build", [s4_assemble.assemble, _lint], BUILD_SHARE),
            ("questions", [s5_questions.ask], 1.0),
        ]
        for sid, stages, share in later:
            # With the verifier off, S3b only records "not run"; the stepper says it was skipped.
            skipped = sid == "verify" and not ctx.verifier_enabled
            if not skipped:
                progress.start(sid)
            for stage in stages:
                if isinstance(
                    outcome := _run(stage, config, sessions, ctx, version.id, job_id), Err
                ):
                    return failed(outcome)
            if skipped:
                progress.skip(sid)
            else:
                progress.done(sid)
            progress.progress(share)
    except Exception:
        failed(Err(ErrorKind.IO, UNEXPECTED))
        raise

    kept_note = ""
    record = run_records.made_with(ctx).model_dump()
    with session_scope(sessions) as session:
        if refreshing and earlier is not None:
            before_record = versions.run_record(session, earlier.id)
            changed = refresh.fold(session, earlier.id, version.id)
            kept = changed.kept
            versions.set_label(session, earlier.id, version.label)
            versions.set_run_record(session, earlier.id, record)
            versions.delete(session, version.id)
            audit.record(
                session,
                actor=actor_name(config),
                action="Refreshed draft from sources",
                target_type="version",
                target_id=earlier.id,
                engagement_id=engagement_id,
                version_id=earlier.id,
                before={"label": earlier.label, "run_record": before_record},
                after={
                    "label": version.label,
                    "kept_steps": kept,
                    "run_record": record,
                    "changes": changed.model_dump(),
                },
            )
            result_id = earlier.id
            kept_note = (
                f" {_plural(kept, 'step')} you reviewed stayed as they were. {_changed(changed)}"
            )
        else:
            # The new draft replaces an earlier one none of whose steps has been reviewed yet.
            for old in versions.drafts(session, engagement_id):
                if old.id != version.id and versions.reviewed_count(session, old.id) == 0:
                    versions.delete(session, old.id)
            versions.set_run_record(session, version.id, record)
            result_id = version.id
        # PDF pictures suggested on the steps whose verified evidence cites their page (P8).
        images_action.attach_suggestions(session, result_id)
        # Cause-library entries for contested and trace-contradicted steps (P9).
        causes.collect(session, result_id)
    if refreshing:
        versions_action.lint_version(sessions, result_id)
    with session_scope(sessions) as session:
        summary = _summary(session, result_id)
    return Ok(
        f"Draft {version.label} is ready: {_plural(summary.steps, 'step')} drafted, "
        f"{summary.needs_check} to check, {_plural(summary.rejected, 'rejected claim')}, "
        f"{_plural(summary.open_questions, 'open question')}.{kept_note}"
    )


# --- Reporting ---------------------------------------------------------------------------------


def _changed(changed: RefreshChanges) -> str:
    """What the refresh drafted differently among the steps not yet reviewed, in one sentence."""
    parts = [
        f"{_plural(len(changed.new_steps), 'new step')}" if changed.new_steps else "",
        f"{_plural(len(changed.no_longer_drafted), 'step')} no longer drafted"
        if changed.no_longer_drafted
        else "",
        f"{len(changed.renamed)} renamed" if changed.renamed else "",
    ]
    listed = [p for p in parts if p]
    if not listed:
        return "The steps you hadn't reviewed came out the same as before."
    return f"Among the steps you hadn't reviewed: {', '.join(listed)}."


def last_refresh(session: Session, job: JobView | None, version_id: str) -> RefreshChanges | None:
    """What the latest refresh changed, when the newest map job is a finished refresh of this
    draft (from its audit row)."""
    if job is None or job.type != REFRESH_JOB or job.status != "done":
        return None
    if job.target_id != version_id:
        return None
    for row in audit.list_for_version(session, version_id):
        if row["action"] == "Refreshed draft from sources":
            stored = (row["after"] or {}).get("changes")
            return RefreshChanges.model_validate(stored) if stored else None
    return None


def _summary(session: Session, version_id: str) -> DraftSummary:
    counts = claims.counts(session, version_id)
    steps, needs_check = map_repo.step_counts(session, version_id)
    return DraftSummary(
        steps=steps,
        needs_check=needs_check,
        verified=counts.get("verified", 0),
        rejected=counts.get("rejected", 0),
        open_questions=map_repo.open_question_count(session, version_id),
        scrubbed=claims.scrub_count(session, version_id),
    )


def with_progress(session: Session, job: JobView) -> JobView:
    """A draft job with its token usage and the claims checked so far (API_CONTRACT → Jobs)."""
    if job.type not in MAP_JOBS:
        return job
    usage = ai_calls.usage_for_job(session, job.id)
    checked = JobClaims()
    target = job.target_id
    if job.type == REFRESH_JOB and job.engagement_id:  # claims are checked into the new version
        half = versions.building(session, job.engagement_id)
        target = half[0].id if half else None
    if target and versions.get(session, target) is not None:
        counts = claims.counts(session, target)
        checked = JobClaims(verified=counts.get("verified", 0), rejected=counts.get("rejected", 0))
    return job.model_copy(update={"usage": usage, "claims": checked})


def get_draft(sessions: Sessions, engagement_id: str) -> Result[DraftState]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        job = _latest_map_job(session, engagement_id)
        unfinished = job is not None and job.status in jobs_repo.UNFINISHED
        # A new draft being made isn't shown until it is done; a refreshed draft stays shown.
        building = job.target_id if job and unfinished and job.type == DRAFT_JOB else None
        current: VersionView | None = next(
            (v for v in versions.drafts(session, engagement_id) if v.id != building), None
        )
        return Ok(
            DraftState(
                job=with_progress(session, job) if job else None,
                version=current,
                summary=_summary(session, current.id) if current else None,
                last_refresh=last_refresh(session, job, current.id) if current else None,
            )
        )


def rejected_claims(sessions: Sessions, version_id: str) -> Result[RejectedClaims]:
    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        terms = redaction.name_replacements(session, version.engagement_id)
        rows = claims.rejected_rows(session, version_id)
        cited = sources_repo.segment_rows(
            session, [sid for _, record in rows for sid in record.segment_ids]
        )
        names: dict[str, str] = {}
        items = []
        for claim_id, record in rows:
            if record.source_id not in names:
                source = sources_repo.get(session, record.source_id)
                names[record.source_id] = source.filename if source else ""
            first = next((cited[s] for s in record.segment_ids if s in cited), None)
            anchor = ""
            if first is not None:
                seg, fmt = first
                anchor = parsing.segment_anchor(
                    fmt=fmt,
                    seq=seg.seq,
                    page=seg.page,
                    section=seg.section,
                    text=seg.text,
                    start_ms=seg.start_ms,
                )
            items.append(
                RejectedClaim(
                    id=claim_id,
                    claim_text=redaction.hide(str(record.payload.get("text", "")), terms),
                    source_id=record.source_id,
                    source_name=redaction.hide(names[record.source_id], terms),
                    anchor=anchor,
                    reason=redaction.hide(record.rejection_reason, terms),
                    guardrail=record.rejection_guardrail,
                    stage=record.stage,
                    passage_available=first is not None,
                    segment_id=first[0].id if first else None,
                )
            )
        return Ok(
            RejectedClaims(
                items=items,
                total=len(items),
                scrub_count=claims.scrub_count(session, version_id),
                instruction_like_count=sources_repo.instruction_like_count(
                    session, version.engagement_id
                ),
            )
        )
