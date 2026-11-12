"""Gap analysis (PRD §3.11, API_CONTRACT → Gap analysis; phase P10): start, run and report.

Advisory and on demand (constraint 22): an analysis runs only when Eric starts it, and nothing
here changes the map. Analysis A (documents vs practice) runs as a background job of type
`gap_internal`; Analysis B (external best practice) starts as a brief Eric edits and approves, and
runs as a job of type `gap_external` only once the brief is confirmed and scan-clean and web
research is switched on. Each job's target is the analysis.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.actions import map_edits, redaction, system_trace
from app.actions import versions as versions_action
from app.actions.draft import now_iso
from app.actions.engagements import actor_name
from app.actions.settings import effective_settings
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.compass import GradeBody, GradeView
from app.domain.gap import (
    Brief,
    BriefPatch,
    BriefState,
    FindingDecision,
    GapAnalysisRecord,
    GapAnalysisView,
    GapBriefView,
    GapCounts,
    GapElementRef,
    GapFindingView,
    GapReport,
    GapStarted,
    GapStep,
    GapUsage,
    NewGapFinding,
    ScanResult,
    StoredGapFinding,
)
from app.domain.graph import QuestionRecord
from app.domain.models import CauseRecord, ExportFile, JobStage, NewStep
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import ga_internal, gb_external
from app.pipeline.context import AiContext, ai_context
from app.repositories import ai_calls, audit
from app.repositories import causes as causes_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import gap as repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo
from app.services import gap as gap_rules
from app.services import gap_report, grounding
from app.services import grade as grade_rules

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

INTERNAL_JOB = "gap_internal"
EXTERNAL_JOB = "gap_external"
GAP_JOBS = (INTERNAL_JOB, EXTERNAL_JOB)
VERSION_MISSING = "That version doesn't exist."
ANALYSIS_MISSING = "That gap analysis doesn't exist."
BUSY = "A gap analysis is already running for this version."
ALREADY_RAN = "This analysis has already run. Start a new one to change the brief."
ALREADY_RUN = "This analysis has already run. Start a new one to run the research again."
NOT_CONFIRMED = (
    "Tick “This brief contains no confidential information” before running the research."
)
HAS_HITS = "Remove the highlighted items from the brief before running the research."
RESEARCH_OFF = "Web research is switched off. Turn it on in Settings first."
BOTH_LISTS = "Use allowed domains or blocked domains, not both."
EDITABLE = ("brief_draft", "failed")
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
EXTERNAL_STAGES = (
    ("research", gb_external.STAGE_NAMES[gb_external.RESEARCH_STAGE]),
    ("structure", gb_external.STAGE_NAMES[gb_external.STRUCTURE_STAGE]),
    ("check", "Checking every finding against its sources"),
    ("verify", "Independent verification"),
    ("report", "Writing the report"),
)
STAGES_BY_JOB = {INTERNAL_JOB: INTERNAL_STAGES, EXTERNAL_JOB: EXTERNAL_STAGES}
SECTION_ORDER = {"fact": 0, "interpretation": 1, "recommendation": 2}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _stages(job_type: str = INTERNAL_JOB) -> list[JobStage]:
    return [JobStage(id=sid, name=name, status="waiting") for sid, name in STAGES_BY_JOB[job_type]]


def _busy(session: Session, version_id: str) -> Err | None:
    for earlier in repo.for_version(session, version_id):
        if earlier.status in {"queued", "running"}:
            return Err(ErrorKind.CONFLICT, BUSY, {"analysis_id": earlier.id})
    return None


# --- Starting ----------------------------------------------------------------------------------


def start_internal(sessions: Sessions, version_id: str, enqueue: Enqueue) -> Result[GapStarted]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None or version.state == "building":
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        if (busy := _busy(session, version_id)) is not None:
            return busy
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


def _brief_state(record: GapAnalysisRecord) -> BriefState | None:
    if record.mode != "external" or record.brief is None:
        return None
    brief = Brief.model_validate(record.brief)
    return BriefState(
        brief=brief,
        text=gap_rules.brief_text(brief),
        confirmed=record.brief_confirmed,
        scan=ScanResult.model_validate(record.brief_scan or {"hits": []}),
    )


def start_external(sessions: Sessions, version_id: str) -> Result[GapBriefView]:
    """Analysis B begins as a drafted brief. No AI call; nothing is sent."""
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        facts = gb_external.brief_facts(session, version_id) if version else None
        inputs = gb_external.scan_inputs(session, version_id) if version else None
        if version is None or version.state == "building" or facts is None or inputs is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        state = gb_external.brief_state(gap_rules.build_brief(facts), False, inputs)
        analysis = repo.create(
            session,
            version_id=version_id,
            mode="external",
            status="brief_draft",
            brief=state.brief.model_dump(),
            brief_scan=state.scan.model_dump(),
        )
        return Ok(GapBriefView(analysis=_view(session, analysis), brief=state))


def update_brief(sessions: Sessions, analysis_id: str, patch: BriefPatch) -> Result[GapBriefView]:
    if patch.brief.allowed_domains and patch.brief.blocked_domains:
        return Err(ErrorKind.VALIDATION, BOTH_LISTS, {"field": "brief.blocked_domains"})
    with session_scope(sessions) as session:
        analysis = repo.get(session, analysis_id)
        if analysis is None:
            return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
        if analysis.mode != "external" or analysis.status not in EDITABLE:
            return Err(ErrorKind.CONFLICT, ALREADY_RAN)
        inputs = gb_external.scan_inputs(session, analysis.version_id)
        if inputs is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        state = gb_external.brief_state(patch.brief, patch.confirmed, inputs)
        saved = repo.set_brief(
            session,
            analysis_id,
            brief=state.brief.model_dump(),
            confirmed=patch.confirmed,
            scan=state.scan.model_dump(),
        )
        return Ok(GapBriefView(analysis=_view(session, saved), brief=state))


def _research_settings(config: AppConfig) -> Result[tuple[bool, int]]:
    """(web research switched on, the most searches one run may use)."""
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    enabled = values["WEB_RESEARCH_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
    cap = values["WEB_SEARCH_MAX_USES_CAP"].strip()
    return Ok((enabled, int(cap) if cap.isdigit() else 20))


def run_external(
    config: AppConfig, sessions: Sessions, analysis_id: str, enqueue: Enqueue
) -> Result[GapStarted]:
    """Nothing is sent while web research is off, the brief is unconfirmed or it has scan hits."""
    with session_scope(sessions) as session:
        analysis = repo.get(session, analysis_id)
        if analysis is None:
            return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
        if analysis.mode != "external" or analysis.status not in EDITABLE:
            return Err(ErrorKind.CONFLICT, ALREADY_RUN)
    match _research_settings(config):
        case Err() as err:
            return err
        case Ok(value=(enabled, _cap)):
            pass
    if not enabled:
        return Err(ErrorKind.CONFLICT, RESEARCH_OFF, api_code="WEB_RESEARCH_DISABLED")
    with session_scope(sessions) as session:
        state = _brief_state(analysis)
        inputs = gb_external.scan_inputs(session, analysis.version_id)
        version = versions_repo.get(session, analysis.version_id)
        if state is None or inputs is None or version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        # Scanned again now: names or confidential terms may have been added since.
        fresh = gb_external.brief_state(state.brief, state.confirmed, inputs)
        repo.set_brief(
            session,
            analysis_id,
            brief=fresh.brief.model_dump(),
            confirmed=fresh.confirmed,
            scan=fresh.scan.model_dump(),
        )
        if not fresh.confirmed:
            return Err(ErrorKind.CONFLICT, NOT_CONFIRMED, api_code="BRIEF_NOT_APPROVED")
        if fresh.scan.hits:
            return Err(
                ErrorKind.CONFLICT,
                HAS_HITS,
                {"hits": [h.model_dump() for h in fresh.scan.hits]},
                api_code="BRIEF_NOT_APPROVED",
            )
        if (busy := _busy(session, analysis.version_id)) is not None:
            return busy
        repo.set_status(session, analysis_id, "queued")
        job = jobs_repo.create(
            session,
            engagement_id=version.engagement_id,
            job_type=EXTERNAL_JOB,
            target_id=analysis_id,
            stages=_stages(EXTERNAL_JOB),
        )
    enqueue(job.id)
    return Ok(GapStarted(analysis_id=analysis_id, job_id=job.id))


# --- Running -----------------------------------------------------------------------------------


class _Progress:
    def __init__(self, sessions: Sessions, job_id: str, job_type: str) -> None:
        self.sessions = sessions
        self.job_id = job_id
        self.stages = _stages(job_type)

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


def _plural(n: int, word: str, words: str = "") -> str:
    return f"{n} {word}" if n == 1 else f"{n} {words or word + 's'}"


def run_analysis(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """Run one gap analysis job. On failure the analysis is `failed` with no findings."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        analysis = repo.get(session, job.target_id or "") if job else None
    if job is None or analysis is None:
        return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
    progress = _Progress(sessions, job_id, job.type)

    def failed(err: Err) -> Err:
        progress.fail()
        with session_scope(sessions) as session:
            repo.replace_findings(session, analysis.id, [])
            repo.replace_sources(session, analysis.id, [], [])
            repo.set_status(session, analysis.id, "failed")
        return err

    with session_scope(sessions) as session:
        repo.set_status(session, analysis.id, "running")
    progress.mark(progress.stages[0].id, "running")
    match ai_context(config):
        case Err() as err:
            return failed(err)
        case Ok(value=ctx):
            pass
    try:
        if job.type == EXTERNAL_JOB:
            return _run_external(config, sessions, ctx, analysis, progress, failed)
        return _run_internal(sessions, ctx, analysis, progress, failed)
    except Exception:
        failed(Err(ErrorKind.IO, UNEXPECTED))
        raise


Failed = Callable[[Err], Err]


def _run_internal(
    sessions: Sessions,
    ctx: AiContext,
    analysis: GapAnalysisRecord,
    progress: _Progress,
    failed: Failed,
) -> Result[str]:
    job_id = progress.job_id
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
        findings += _system_findings(session, analysis.version_id, findings)
        repo.replace_findings(session, analysis.id, findings)
        repo.set_status(session, analysis.id, "draft_report", model=ctx.model)
    progress.mark("report", "done", 1.0)
    kept = [f for f in findings if f.verification_status != "rejected" and not f.question]
    questions = [f for f in findings if f.question]
    rejected = len(findings) - len(kept) - len(questions)
    return Ok(
        f"The documents-vs-practice report is ready: {_plural(len(kept), 'finding')}, "
        f"{_plural(len(questions), 'question')} for your SMEs, "
        f"{_plural(rejected, 'rejected finding')}."
    )


def _system_findings(session: Session, version_id: str,
                     findings: list[NewGapFinding]) -> list[NewGapFinding]:  # fmt: skip
    """System-record facts from Eric's confirmed alignment (§3.13.6, R6); Claude's dead-control
    findings gain the system's silence as evidence. Without imported logs: nothing."""
    version = versions_repo.get(session, version_id)
    graph = versions_action.build_graph(session, version_id) if version else None
    if version is None or graph is None:
        return []
    keys = {e.id: e.stable_key for e in map_repo.elements(session, version_id)}
    dead = [f for f in findings if f.finding_type == "dead_control_candidate"
            and f.verification_status != "rejected"]  # fmt: skip
    ai_dead = {keys[i] for f in dead for i in f.element_ids if i in keys}
    extra = system_trace.system_findings(session, version, graph, ai_dead)
    for f in dead:
        for i in f.element_ids:
            support = extra.dead_control_support.get(keys.get(i, ""))
            if support is not None and support[1] not in f.notes:
                f.evidence.append(support[0])
                f.notes.append(support[1])
    return extra.findings


def _run_external(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    analysis: GapAnalysisRecord,
    progress: _Progress,
    failed: Failed,
) -> Result[str]:
    job_id = progress.job_id
    match _research_settings(config):
        case Err() as err:
            return failed(err)
        case Ok(value=(_enabled, cap)):
            pass
    state = _brief_state(analysis)
    if state is None:
        return failed(Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING))
    brief = state.brief
    match gb_external.research(sessions, ctx, brief, cap, job_id):
        case Err() as err:
            return failed(err)
        case Ok(value=answer):
            pass
    captured = gb_external.capture(answer)
    with session_scope(sessions) as session:
        repo.replace_sources(session, analysis.id, captured.sources, captured.citation_rows())
        repo.set_outcome(
            session, analysis.id, search_count=answer.search_count, notes=captured.notes
        )
        version = versions_repo.get(session, analysis.version_id)
        terms = redaction.name_replacements(session, version.engagement_id) if version else []
        roles = engagements_repo.list_roles(session, version.engagement_id) if version else []
        steps = gb_external.step_refs(gb_external.steps_of(session, analysis.version_id))
    progress.mark("research", "done", 0.4)

    progress.mark("structure", "running")
    findings_in: list[ai_schemas.GBFinding] = []
    if captured.answer:
        blocks = gb_external.structure_blocks(captured, steps, {r.id: r.name for r in roles})
        match gb_external.structure(sessions, ctx, blocks, job_id):
            case Err() as err:
                return failed(err)
            case Ok(value=output):
                findings_in = output.findings
    progress.mark("structure", "done", 0.6)

    progress.mark("check", "running")
    checked = [
        gb_external.check(
            captured,
            steps,
            f,
            recency_years=brief.recency_years,
            this_year=date.today().year,
            terms=terms,
        )
        for f in findings_in
    ]
    progress.mark("check", "done", 0.65)

    if ctx.verifier_enabled:
        progress.mark("verify", "running")
        outcome = gb_external.verify(sessions, ctx, captured, checked, terms, job_id)
        if isinstance(outcome, Err):
            return failed(outcome)
        progress.mark("verify", "done", 0.9)
    else:
        progress.mark("verify", "skipped", 0.9)

    progress.mark("report", "running")
    findings, left_out = gb_external.report(checked)
    with session_scope(sessions) as session:
        repo.replace_findings(session, analysis.id, findings)
        repo.set_outcome(
            session,
            analysis.id,
            search_count=answer.search_count,
            notes=captured.notes + left_out,
        )
        repo.set_status(session, analysis.id, "draft_report", model=ctx.model)
    progress.mark("report", "done", 1.0)
    kept = [f for f in findings if f.verification_status != "rejected"]
    partial = " Some results may be missing: see the notes." if captured.notes else ""
    return Ok(
        f"The external best-practice report is ready: {_plural(len(kept), 'finding')}, "
        f"{_plural(len(findings) - len(kept), 'rejected finding')}, "
        f"{_plural(answer.search_count, 'search', 'searches')} used.{partial}"
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
        notes=list(analysis.notes),
        counts=_counts(repo.findings(session, analysis.id)),
    )


def list_analyses(sessions: Sessions, version_id: str) -> Result[list[GapAnalysisView]]:
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        return Ok([_view(session, a) for a in repo.for_version(session, version_id)])


def _finding_view(f: StoredGapFinding, labels: dict[str, str]) -> GapFindingView:
    needs_check = f.verifier_verdict == "partial"
    speaking = [e for e in f.evidence if e.stance != "silent"]
    suggested = grade_rules.for_gap_finding(
        provenance=f.provenance, verification_status=f.verification_status,
        needs_check=needs_check, system=any(e.side == "system" for e in speaking),
        others=len({e.source_id or e.url for e in speaking if e.side != "system"}),
    )  # fmt: skip
    return GapFindingView(
        **f.model_dump(exclude={"evidence", "grade_chosen"}),
        evidence=f.evidence,
        elements=[GapElementRef(id=e, label=labels.get(e, "")) for e in f.element_ids],
        needs_check=needs_check,
        grade=GradeView(grade=f.grade_chosen or suggested, suggested=suggested,
                        chosen_by_owner=f.grade_chosen is not None,
                        rules_version=grade_rules.GRADE_RULES_VERSION),
    )  # fmt: skip


BAD_GRADE = "Choose Confirmed, Indicated or Hypothesis."


def set_grade(config: AppConfig, sessions: Sessions, finding_id: str,
              body: GradeBody) -> Result[GapFindingView]:  # fmt: skip
    """Eric's own grade for a gap finding, or back to the suggested grade with null. The grade
    changes nothing else: provenance, checks and the map stay as they are."""
    if body.grade is not None and body.grade not in grade_rules.GRADES:
        return Err(ErrorKind.VALIDATION, BAD_GRADE, {"field": "grade"})
    with session_scope(sessions) as session:
        found = repo.finding(session, finding_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, FINDING_MISSING)
        analysis_id, f = found
        analysis = repo.get(session, analysis_id)
        version = versions_repo.get(session, analysis.version_id) if analysis else None
        if analysis is not None and analysis.status == "finalised":
            return Err(ErrorKind.CONFLICT, FINALISED)
        if f.grade_chosen != body.grade:
            updated = repo.set_grade(session, finding_id, body.grade)
            audit.record(session, actor=actor_name(config), action="Set gap finding grade",
                         target_type="gap_finding", target_id=finding_id,
                         engagement_id=version.engagement_id if version else None,
                         before={"grade": f.grade_chosen}, after={"grade": body.grade})  # fmt: skip
            f = updated
        labels = ({e.id: e.label for e in map_repo.elements(session, version.id)}
                  if version else {})  # fmt: skip
        return Ok(_finding_view(f, labels))


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
        sources = repo.sources(session, analysis_id)
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
            questions=[f for f in kept if f.question],
            sources=sources,
            brief=_brief_state(analysis),
            usage=GapUsage(**usage) if usage else None,
            search_count=analysis.search_count,
        )
    )


# --- Dispositions, finalising and the export (PRD §3.11.3) --------------------------------------

FINDING_MISSING = "That finding doesn't exist."
FINALISED = "This report is finalised and can't be changed."
DECIDED = "This finding already has a decision."
REJECTED = "A rejected finding can't be used."
NO_DRAFT = "Reopen this map as a new draft first: questions and steps are added to the draft."
NOTE_NEEDED = "Say why you're dismissing this finding."
CAUSE_EXTERNAL = "Only documents-vs-practice findings go to the cause library."
CAUSE_NO_STEP = "This finding isn't tied to a step, so it can't go to the cause library."
BAD_DISPOSITION = "Choose added_question, added_cause, added_step or dismissed."
STEP_NEEDED = "Choose where the new step goes."
NOT_DRAFT_REPORT = "Only a draft report can be finalised."
NOT_FINALISED = "Finalise the report first."
NAME_IN_EXPORT = (
    "The report still contained a name from your list of names to hide, so it wasn't exported. "
    "Use Copy details to report it."
)
DIVERGENCE_OF = {
    "threshold_gap": "threshold",
    "ownership_mismatch": "ownership",
    "sequence_gap": "sequence",
    "trigger_gap": "trigger",
    "exception_gap": "exception",
}
NO_GAP_CLASS = "Only reality-gap findings have a gap class."
AUDIT_ACTIONS = {
    "added_question": "Added gap finding as question",
    "added_cause": "Added gap finding to cause library",
    "added_step": "Added step from gap finding",
    "dismissed": "Dismissed gap finding",
}


def _question_text(mode: str, f: StoredGapFinding) -> str:
    if f.question:
        return f.question
    if mode == "internal":
        return f"{f.title}: which account is right in practice?"
    return f"Should the process include this practice: {f.title}?"


def _new_step(mode: str, f: StoredGapFinding, step: GapStep) -> NewStep:
    """The Add step request, with provenance and evidence from the finding (Eric's step)."""
    if mode == "external":
        first = next((e for e in f.evidence if e.url), None)
        reference = f"{first.source_name} {first.url}".strip() if first else f.title
        return NewStep(**step.model_dump(), provenance="R", r_reference=reference[:500])
    segments = [e.segment_id for e in f.evidence if e.segment_id]
    return NewStep(**step.model_dump(), provenance="O", segment_ids=segments)


def decide(
    config: AppConfig, sessions: Sessions, finding_id: str, decision: FindingDecision
) -> Result[GapFindingView]:
    kind = decision.disposition
    if kind not in AUDIT_ACTIONS:
        return Err(ErrorKind.VALIDATION, BAD_DISPOSITION, {"field": "disposition"})
    note = decision.note.strip()
    if kind == "dismissed" and not note:
        return Err(ErrorKind.VALIDATION, NOTE_NEEDED, {"field": "note"})
    with session_scope(sessions) as session:
        found = repo.finding(session, finding_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, FINDING_MISSING)
        analysis_id, f = found
        analysis = repo.get(session, analysis_id)
        version = versions_repo.get(session, analysis.version_id) if analysis else None
        if analysis is None or version is None:
            return Err(ErrorKind.NOT_FOUND, FINDING_MISSING)
        if analysis.status == "finalised":
            return Err(ErrorKind.CONFLICT, FINALISED)
        if f.verification_status == "rejected":
            return Err(ErrorKind.CONFLICT, REJECTED)
        if f.disposition != "open":
            return Err(ErrorKind.CONFLICT, DECIDED)
        if decision.gap_class is not None and f.gap_class is None:
            return Err(ErrorKind.VALIDATION, NO_GAP_CLASS, {"field": "gap_class"})
        keys = {e.id: e.stable_key for e in map_repo.elements(session, version.id)}
        first_key = next((keys[e] for e in f.element_ids if e in keys), None)
        draft = versions_repo.current_draft(session, version.engagement_id)
        if kind in {"added_question", "added_step"} and draft is None:
            return Err(ErrorKind.CONFLICT, NO_DRAFT)
        if kind == "added_cause" and analysis.mode != "internal":
            return Err(ErrorKind.VALIDATION, CAUSE_EXTERNAL, {"field": "disposition"})
        if kind == "added_cause" and first_key is None:
            return Err(ErrorKind.VALIDATION, CAUSE_NO_STEP, {"field": "disposition"})
        if kind == "added_step" and decision.step is None:
            return Err(ErrorKind.VALIDATION, STEP_NEEDED, {"field": "step"})
    ref = ""
    if kind == "added_step":
        assert draft is not None and decision.step is not None
        added = map_edits.add_step(
            config, sessions, draft.id, _new_step(analysis.mode, f, decision.step)
        )
        if isinstance(added, Err):
            return added
        ref = f"element:{added.value.id}"
    with session_scope(sessions) as session:
        if kind == "added_question":
            assert draft is not None
            target = next(
                (e for e in map_repo.elements(session, draft.id) if e.stable_key == first_key),
                None,
            )
            [question] = map_repo.add_questions(
                session,
                draft.id,
                [
                    QuestionRecord(
                        element_id=target.id if target else None,
                        phase_id=target.phase_id if target else None,
                        question=_question_text(analysis.mode, f),
                        reason="gap_analysis",
                        origin_ref=f.id,
                    )
                ],
            )
            ref = f"question:{question.id}"
        elif kind == "added_cause":
            assert first_key is not None
            divergence = DIVERGENCE_OF.get(f.finding_type, "omission")
            existing = next(
                (
                    c
                    for c in causes_repo.for_engagement(session, version.engagement_id)
                    if (c.element_stable_key, c.divergence_type) == (first_key, divergence)
                ),
                None,
            )
            cause = existing or causes_repo.add(
                session,
                CauseRecord(
                    engagement_id=version.engagement_id,
                    element_stable_key=first_key,
                    divergence_type=divergence,
                    pattern=f.text,
                    inferred_cause=f.basis if f.section == "interpretation" else "",
                    provenance="I" if f.section == "interpretation" else "O",
                ),
            )
            ref = f"cause:{cause.id}"
        final = decision.gap_class.value if decision.gap_class else None
        saved = repo.set_disposition(session, f.id, kind, note, ref, final)
        audit.record(
            session,
            actor=actor_name(config),
            action=AUDIT_ACTIONS[kind],
            target_type="gap_finding",
            target_id=f.id,
            engagement_id=version.engagement_id,
            version_id=draft.id if draft and kind != "dismissed" else version.id,
            before={"disposition": "open"} | ({"gap_class": f.gap_class} if final else {}),
            after={"disposition": kind, "note": note, "created_item_ref": ref}
            | ({"gap_class": final} if final else {}),
        )
        terms = redaction.name_replacements(session, version.engagement_id)
        labels = {
            e.id: redaction.hide(e.label, terms) for e in map_repo.elements(session, version.id)
        }
    return Ok(_finding_view(saved, labels))


def finalise(config: AppConfig, sessions: Sessions, analysis_id: str) -> Result[GapReport]:
    with session_scope(sessions) as session:
        analysis = repo.get(session, analysis_id)
        if analysis is None:
            return Err(ErrorKind.NOT_FOUND, ANALYSIS_MISSING)
        if analysis.status != "draft_report":
            return Err(ErrorKind.CONFLICT, NOT_DRAFT_REPORT)
        still = [
            f
            for f in repo.findings(session, analysis_id)
            if f.verification_status != "rejected" and f.disposition == "open"
        ]
        if still:
            return Err(
                ErrorKind.CONFLICT,
                f"Decide on every finding first: {len(still)} still open.",
                {"open": len(still)},
            )
        repo.finalise(session, analysis_id)
        version = versions_repo.get(session, analysis.version_id)
        audit.record(
            session,
            actor=actor_name(config),
            action="Finalised gap report",
            target_type="gap_analysis",
            target_id=analysis_id,
            engagement_id=version.engagement_id if version else None,
            version_id=analysis.version_id,
        )
    return get_report(sessions, analysis_id)


def export_report(sessions: Sessions, analysis_id: str) -> Result[ExportFile]:
    match get_report(sessions, analysis_id):
        case Err() as err:
            return err
        case Ok(value=report):
            pass
    if report.analysis.status != "finalised":
        return Err(ErrorKind.CONFLICT, NOT_FINALISED)
    with session_scope(sessions) as session:
        version = versions_repo.get(session, report.analysis.version_id)
        engagement = engagements_repo.get(session, version.engagement_id) if version else None
        terms = redaction.name_replacements(session, version.engagement_id) if version else []
    name = (engagement.process_name or engagement.name) if engagement else "Process"
    text = gap_report.render_report_md(report, redaction.hide(name, terms))
    if grounding.scan_redaction_terms(text, [t.term for t in terms]):
        return Err(ErrorKind.IO, NAME_IN_EXPORT)
    label = report.analysis.version_label.replace(" ", "-")
    return Ok(
        ExportFile(
            filename=f"gap-analysis-{report.analysis.mode}-{label}.md",
            media_type="text/markdown; charset=utf-8",
            content=text,
        )
    )
