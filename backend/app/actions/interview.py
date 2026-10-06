"""Interview tools for one engagement (PRD §3.12.8, Appendix F.8; phase P4c).

C5a: interviewee profiles — whose interview a tailored guide is for: a role, function or
stakeholder group, never a person (constraint 10). Every change writes an audit row.
G1: tailored guides — the standard template of the profile's type, filled in from the profile,
the scope card and the latest map (F.8 rules 1, 2, 5, 7, 8), versioned and exported like the
templates. Deterministic; nothing is sent to Claude.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions import coverage, questions, redaction, versions
from app.actions.draft import now_iso
from app.actions.engagements import actor_name
from app.actions.interview_templates import MEDIA, UNKNOWN_FORMAT
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import InterviewType
from app.domain.interview import (
    DocumentRow,
    GuideContext,
    GuideInput,
    GuideStarted,
    GuideSummary,
    GuideView,
    InterviewDocument,
    ProfileInput,
    ProfilePatch,
    ProfileView,
    QuestionBank,
    TemplateFile,
)
from app.domain.models import JobStage, NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import ig_generate
from app.pipeline.context import ai_context
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import interview as interview_repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo
from app.services import grounding
from app.services import interview_templates as templates
from app.services.alignment import STEPS

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

ENGAGEMENT_MISSING = "That engagement doesn't exist."
PROFILE_MISSING = "That interviewee profile doesn't exist."
MAX_TEXT = 120
TEXTS = {"stakeholder_group": "The stakeholder group", "referred_by_role": "Referred by"}
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."
PROFILE_ELSEWHERE = "Choose one of this engagement's interviewees."
NO_GUIDE = "No guide yet for this interviewee."


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _check(session: Session, engagement_id: str, profile_id: str | None,
           fields: dict[str, Any]) -> Result[dict[str, Any]]:  # fmt: skip
    """The profile's fields, tidied, or the first problem naming its field."""
    if fields["interview_type"] not in {t.value for t in InterviewType}:
        return _invalid("interview_type", "Choose landscape, practice or follow-up.")
    roles = {r.id for r in engagements_repo.list_roles(session, engagement_id)}
    if fields["role_id"] is not None and fields["role_id"] not in roles:
        return _invalid("role_id", "Choose one of this engagement's roles.")
    hidden = [t.term for t in redaction.name_replacements(session, engagement_id)]
    for field, words in TEXTS.items():
        text = str(fields[field] or "").strip()
        if len(text) > MAX_TEXT or "\n" in text:
            return _invalid(field, f"{words} can be up to {MAX_TEXT} characters on one line.")
        if grounding.scan_redaction_terms(text, hidden):  # the name itself is never echoed
            return _invalid(field, HIDDEN_NAME.format(what=words))
        fields[field] = text
    if fields["role_id"] is None and not fields["stakeholder_group"]:
        return _invalid(
            "role_id", "Say whose interview this is: choose a role or name the stakeholder group."
        )
    previous = fields["previous_profile_id"]
    if previous is not None:
        earlier = interview_repo.profile(session, previous)
        if earlier is None or earlier.engagement_id != engagement_id or previous == profile_id:
            return _invalid(
                "previous_profile_id", "Choose an earlier interview in this engagement."
            )
    return Ok(fields)


def list_profiles(sessions: Sessions, engagement_id: str) -> Result[list[ProfileView]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(interview_repo.profiles(session, engagement_id))


def add_profile(
    config: AppConfig, sessions: Sessions, engagement_id: str, body: ProfileInput
) -> Result[ProfileView]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        checked = _check(session, engagement_id, None, body.model_dump())
        if isinstance(checked, Err):
            return checked
        created = interview_repo.add_profile(session, engagement_id, checked.value)
        audit.record(session, actor=actor_name(config), action="Added interviewee profile",
                     target_type="profile", target_id=created.id, engagement_id=engagement_id,
                     after=checked.value)  # fmt: skip
        return Ok(created)


def edit_profile(
    config: AppConfig, sessions: Sessions, profile_id: str, patch: ProfilePatch
) -> Result[ProfileView]:
    with session_scope(sessions) as session:
        before = interview_repo.profile(session, profile_id)
        if before is None:
            return Err(ErrorKind.NOT_FOUND, PROFILE_MISSING)
        current = before.model_dump(include=set(ProfileInput.model_fields))
        sent = {name: getattr(patch, name) for name in patch.model_fields_set}
        for name in ("stakeholder_group", "referred_by_role", "interview_type"):
            if name in sent and sent[name] is None:
                sent[name] = ""
        checked = _check(session, before.engagement_id, profile_id, current | sent)
        if isinstance(checked, Err):
            return checked
        changed = {k: v for k, v in checked.value.items() if v != current[k]}
        if not changed:
            return Ok(before)
        updated = interview_repo.update_profile(session, profile_id, changed)
        audit.record(session, actor=actor_name(config), action="Edited interviewee profile",
                     target_type="profile", target_id=profile_id,
                     engagement_id=before.engagement_id,
                     before={k: current[k] for k in changed}, after=changed)  # fmt: skip
        return Ok(updated)


# --- Tailored guides (API_CONTRACT.md → Tailored interview guides; F.8; G1) --------------------


def _context(session: Session, engagement_id: str, profile: ProfileView) -> GuideContext:
    """What the guide is filled in from: the profile, the scope card and the latest map's steps
    only the documents describe (names already hidden by the graph)."""
    engagement = engagements_repo.get(session, engagement_id)
    assert engagement is not None
    hidden = [t.term for t in redaction.name_replacements(session, engagement_id)]
    process = engagement.process_name or engagement.name
    scope = f"{process} process" if process else ""  # the opener already says "the"
    if scope and engagement.trigger and engagement.end_point:
        scope += f", from {engagement.trigger} to {engagement.end_point}"
    who = " · ".join(x for x in (profile.role_name, profile.stakeholder_group) if x)
    sop_steps = []
    map_id = versions_repo.current_map_id(session, engagement_id)
    graph = versions.build_graph(session, map_id) if map_id else None
    if graph is not None and profile.interview_type == "practice":
        sop_steps = [
            e.label for e in graph.elements
            if e.kind in STEPS and e.view_membership == "documented_only"
            and e.review_status != "rejected"
        ]  # fmt: skip
    return GuideContext(
        interview_type=InterviewType(profile.interview_type), who=who, process=process, scope=scope,
        business=engagement.name, area=profile.stakeholder_group or profile.role_name,
        referrer_role=profile.referred_by_role, role=profile.role_name,
        stakeholder_group=profile.stakeholder_group, sop_steps=sop_steps, hidden_terms=hidden,
    )  # fmt: skip


def _follow_ups(sessions: Sessions, engagement_id: str, ctx: GuideContext,
                has_earlier: bool) -> Result[GuideContext]:  # fmt: skip
    """Rule 7: the latest map's F2 probes, open validation questions (F6), then its "not
    described" questions (F5); `[topics]` from what the coverage report shows as covered."""
    with session_scope(sessions) as session:
        map_id = versions_repo.current_map_id(session, engagement_id)
        open_questions = (
            [q for q in questions.question_views(session, map_id, engagement_id)
             if q.status == "open"] if map_id else []
        )  # fmt: skip
    if map_id is None:
        return Ok(ctx)
    report = coverage.get_coverage(sessions, map_id)
    if isinstance(report, Err):
        return report
    rows = [(p.question_id, p.question) for p in report.value.probes]
    rows += [("F6", q.question) for q in open_questions if q.reason != "not_described"]
    rows += [("F5", q.question) for q in open_questions if q.reason == "not_described"]
    covered = [name.replace("_", " ") for name, d in report.value.dimensions.items()
               if d.status == "covered"]  # fmt: skip
    topics = ", ".join(covered) if has_earlier else ""
    return Ok(ctx.model_copy(update={"follow_ups": rows, "topics": topics}))


GUIDE_JOB = "interview_guide"
GUIDE_STAGES = (
    ("gather", "Reading the scope, roles and map"),
    ("generate", ig_generate.STAGE_NAME),
    ("check", "Checking every question"),
    ("save", "Saving the guide"),
)
GUIDE_FAILED = (
    "Something went wrong while making this guide. Nothing was saved. "
    "Try again, or use Copy details to report it."
)
MAX_HANDOFFS = 15
NOT_DRAFTED = "The role-module rows are left blank for you: {why}"
NO_QUESTION_KEPT = "none of Claude's questions passed the app's checks."


def make_guide(
    sessions: Sessions, engagement_id: str, body: GuideInput, enqueue: Enqueue
) -> Result[GuideStarted]:
    """Queue a new version of one interviewee's guide (a background job, F.8 rule 3 uses AI)."""
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        profile = interview_repo.profile(session, body.profile_id)
        if profile is None or profile.engagement_id != engagement_id:
            return _invalid("profile_id", PROFILE_ELSEWHERE)
        job = jobs_repo.create(
            session, engagement_id=engagement_id, job_type=GUIDE_JOB, target_id=profile.id,
            stages=[JobStage(id=sid, name=name, status="waiting") for sid, name in GUIDE_STAGES],
        )  # fmt: skip
    enqueue(job.id)
    return Ok(GuideStarted(job_id=job.id, profile_id=profile.id))


class _Stages:
    """The job's stage stepper, saved as each stage starts and ends."""

    def __init__(self, sessions: Sessions, job_id: str) -> None:
        self.sessions, self.job_id = sessions, job_id
        self.stages = [JobStage(id=sid, name=name, status="waiting") for sid, name in GUIDE_STAGES]

    def mark(self, sid: str, status: str) -> None:
        stage = next(s for s in self.stages if s.id == sid)
        stage.status = status
        if status == "running":
            stage.started_at = now_iso()
        else:
            stage.started_at = stage.started_at or now_iso()
            stage.finished_at = now_iso()
        done = sum(1 for s in self.stages if s.status == "done") / len(self.stages)
        with session_scope(self.sessions) as session:
            jobs_repo.update(session, self.job_id, stages=self.stages, progress=done,
                             stage=stage.name if status == "running" else None)  # fmt: skip


def _role_module_input(
    session: Session, engagement_id: str, profile: ProfileView, hidden: list[NameReplacement]
) -> ig_generate.RoleModuleInput:
    """The scope card, roles and the latest map's handoffs involving the interviewee's lane
    (every handoff between lanes when the profile names a group, not a role)."""
    engagement = engagements_repo.get(session, engagement_id)
    assert engagement is not None
    roles = [r.name for r in engagements_repo.list_roles(session, engagement_id)]
    handoffs: list[dict[str, str]] = []
    map_id = versions_repo.current_map_id(session, engagement_id)
    graph = versions.build_graph(session, map_id) if map_id else None  # labels already hidden
    if graph is not None:
        lane = {r.id: r.name for r in graph.roles}
        steps = {e.id: e for e in graph.elements}
        for edge in graph.edges:
            a, b = steps.get(edge.from_), steps.get(edge.to)
            if a is None or b is None or not a.lane_role_id or not b.lane_role_id:
                continue
            if a.lane_role_id == b.lane_role_id:
                continue
            if profile.role_id and profile.role_id not in (a.lane_role_id, b.lane_role_id):
                continue
            handoffs.append(
                {
                    "from_role": lane.get(a.lane_role_id, ""),
                    "step": a.label,
                    "to_role": lane.get(b.lane_role_id, ""),
                    "next_step": b.label,
                }
            )

    def hide(text: str) -> str:
        return redaction.hide(text, hidden)

    return ig_generate.RoleModuleInput(
        group=hide(profile.stakeholder_group or profile.role_name),
        process=hide(engagement.process_name or engagement.name),
        trigger=hide(engagement.trigger), end_point=hide(engagement.end_point),
        roles=[hide(r) for r in roles], handoffs=handoffs[:MAX_HANDOFFS],
    )  # fmt: skip


def _role_module(
    config: AppConfig, sessions: Sessions, bank: QuestionBank, data: ig_generate.RoleModuleInput,
    hidden: list[str], job_id: str, stages: _Stages,
) -> tuple[list[DocumentRow], str, str]:  # fmt: skip
    """(kept rows, note when left blank, audit outcome). Any AI failure leaves the rows blank
    with the reason; the guide is still made (the deterministic guide is the fallback)."""
    stages.mark("generate", "running")
    match ai_context(config):
        case Err(message=why):
            stages.mark("generate", "failed")
            return [], NOT_DRAFTED.format(why=why), "left blank"
        case Ok(value=ctx):
            pass
    proposed = ig_generate.draft_role_module(sessions, ctx, bank, data, job_id)
    if isinstance(proposed, Err):
        stages.mark("generate", "failed")
        return [], NOT_DRAFTED.format(why=proposed.message), "left blank"
    stages.mark("generate", "done")
    stages.mark("check", "running")
    checked = templates.check_role_questions(bank, proposed.value, hidden)
    stages.mark("check", "done")
    if not checked.kept:
        return [], NOT_DRAFTED.format(why=NO_QUESTION_KEPT), "left blank"
    return checked.kept, "", "drafted"


def run_guide(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """Make the guide a job asked for: the deterministic guide (G1), plus for a Landscape
    interview the role module Claude drafts and the app checks."""
    bank = templates.load_bank()
    if isinstance(bank, Err):
        return bank
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        profile = interview_repo.profile(session, job.target_id or "") if job else None
    if job is None or profile is None or job.engagement_id is None:
        return Err(ErrorKind.NOT_FOUND, PROFILE_MISSING)
    engagement_id = job.engagement_id
    stages = _Stages(sessions, job_id)
    stages.mark("gather", "running")
    with session_scope(sessions) as session:
        ctx = _context(session, engagement_id, profile)
        terms = redaction.name_replacements(session, engagement_id)
        landscape = profile.interview_type == InterviewType.LANDSCAPE.value
        data = _role_module_input(session, engagement_id, profile, terms) if landscape else None
    if ctx.interview_type == "follow_up":
        filled = _follow_ups(sessions, engagement_id, ctx, profile.previous_profile_id is not None)
        if isinstance(filled, Err):
            stages.mark("gather", "failed")
            return filled
        ctx = filled.value
    stages.mark("gather", "done")
    document = templates.tailor(bank.value, ctx)
    outcome = "not asked"
    if data is not None:
        rows, note, outcome = _role_module(
            config, sessions, bank.value, data, ctx.hidden_terms, job_id, stages
        )
        document = templates.with_role_module(document, rows, note)
    for sid in ("generate", "check"):
        if next(s for s in stages.stages if s.id == sid).status == "waiting":
            stages.mark(sid, "done")
    stages.mark("save", "running")
    with session_scope(sessions) as session:
        made = interview_repo.add_guide(session, engagement_id, profile.id, document)
        audit.record(session, actor=actor_name(config), action="Made interview guide",
                     target_type="interview_guide", target_id=made.id,
                     engagement_id=engagement_id,
                     after={"profile_id": profile.id, "version": made.version,
                            "interview_type": made.interview_type,
                            "role_module": outcome})  # fmt: skip
    stages.mark("save", "done")
    kept = sum(1 for t in document.tables for r in t.rows if r.id.startswith("RM"))
    message = f"Guide version {made.version} made."
    if outcome == "drafted":
        message += f" {kept} role-module question{'s' if kept != 1 else ''} drafted and checked."
    elif outcome == "left blank":
        message += " " + document.generation_note
    return Ok(message)


def list_guides(sessions: Sessions, engagement_id: str) -> Result[list[GuideSummary]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(interview_repo.latest_guides(session, engagement_id))


def get_guide(sessions: Sessions, engagement_id: str, profile_id: str) -> Result[GuideView]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        guide = interview_repo.latest_guide(session, profile_id)
        if guide is None or guide.engagement_id != engagement_id:
            return Err(ErrorKind.NOT_FOUND, NO_GUIDE)
        return Ok(guide)


def export_guide(
    sessions: Sessions, engagement_id: str, profile_id: str, fmt: str
) -> Result[TemplateFile]:
    if fmt not in MEDIA:
        return _invalid("format", UNKNOWN_FORMAT)
    found = get_guide(sessions, engagement_id, profile_id)
    if isinstance(found, Err):
        return found
    with session_scope(sessions) as session:
        profile = interview_repo.profile(session, profile_id)
        hidden = [t.term for t in redaction.name_replacements(session, engagement_id)]
    doc = found.value.document
    who = profile.role_name or profile.stakeholder_group if profile else ""
    if grounding.scan_redaction_terms(who, hidden):
        who = ""
    return Ok(TemplateFile(filename=templates.guide_filename(doc.kind, who, fmt),
                           media_type=MEDIA[fmt],
                           content=_rendered(fmt, doc.model_dump_json())))  # fmt: skip


@lru_cache(maxsize=32)
def _rendered(fmt: str, document: str) -> bytes:
    """A guide's file, made once per content (a Word file takes about 100 ms to build); keyed by
    the content itself, so a changed guide is never served from an old file."""
    doc = InterviewDocument.model_validate_json(document)
    return templates.render_docx(doc) if fmt == "docx" else templates.render_markdown(doc).encode()
