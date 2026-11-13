"""Comparing countries (API_CONTRACT.md → Comparing countries; PRD §3.19; DECISIONS 98).

Two published maps of the same process in two countries: a reference (e.g. Arden) and an other
(e.g. Belmar). Steps are paired by fixed rules (and, if Eric asks, by Claude, between existing keys
only); Eric decides each pair, by stable key, so his decisions carry through a republish. The
differences of his pairs are worked out by fixed rules; he classes each one (or keeps or dismisses
it) and a classed or kept one gets its `Vn` code in the other engagement. Nothing moves between the
two engagements: each side is read with its own names hidden.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import discrepancies as discrepancies_action
from app.actions import publish, reality_pack, redaction
from app.actions import quality as quality_action
from app.actions import reality as reality_action
from app.actions import versions as versions_action
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.comparisons import (
    Candidate,
    ComparisonCreate,
    ComparisonRecord,
    ComparisonSummary,
    ComparisonView,
    DifferenceCounts,
    DifferenceDecision,
    DifferenceView,
    PairDecision,
    PairView,
    SideView,
    StepView,
    SuggestJob,
    SuggestStarted,
)
from app.domain.compass import GradeView
from app.domain.enums import (
    DifferenceStatus,
    PairStatus,
    ReasonClass,
    SourceKind,
    VersionState,
)
from app.domain.graph import GraphEvidence
from app.domain.models import EngagementView, ExportFile, VersionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import cc_match
from app.pipeline.context import ai_context
from app.repositories import audit
from app.repositories import codes as codes_repo
from app.repositories import comparisons as repo
from app.repositories import engagements as engagements_repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo
from app.services import compass as compass_service
from app.services import compass_return, export_comparison, exports, grounding
from app.services import country_compare as rules
from app.services import grade as grade_rules

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

MATCH_JOB = "country_match"
UNEXPECTED = "Suggesting step pairs stopped unexpectedly. Nothing was saved. Try again."
MISSING = "That comparison doesn't exist. It may have been deleted."
SAME_ENGAGEMENT = "Choose two different engagements."
NO_PUBLISHED = "{name} has no published version yet. Only published maps are compared."
A_DRAFT = "Version {label} of {name} is a draft. Only published maps are compared."
NOT_ITS_VERSION = "That version isn't one of {name}'s."
DIFFERENT = (
    "These maps describe different processes ({a} and {b}). Only maps of the same process in two "
    "countries are compared."
)
BAD_DECISION = "Choose Confirm, Only in one country, or Clear."
CHOOSE_STEPS = "Choose a step of each map."
NOT_ON_MAP = "That step isn't on the compared map."
BAD_ACTION = "Choose Class, Keep, Dismiss or Reopen."
BAD_REASON = "Choose Required, Chosen, Inherited or Not known yet."
NEEDS_REASON = "Add one line saying why."
NEEDS_NOTE = "Add a note saying why this isn't a real difference."
BAD_LINE = "Keep it to one line of up to 300 characters."
BAD_GRADE = "Choose Confirmed, Indicated or Hypothesis."
HIDDEN = "{what} contains a name from your list of names to hide. Use the role instead."
NO_DIFFERENCE = "That difference isn't in this comparison."
BUSY = "Claude is already suggesting pairs for this comparison. Wait for it to finish."
NOTHING_TO_SUGGEST = "Every step is already paired or decided: there is nothing to suggest."
SUGGESTED = "Claude suggested {n} {pairs} for you to check."
LEFT_OUT = " {n} {suggestions} left out because {it} named a step that isn't unpaired on the map."
MAX_LINE = 300
PUBLISHED = (VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value)
DECIDED = (PairStatus.CONFIRMED.value, PairStatus.ONLY_REFERENCE.value, PairStatus.ONLY_OTHER.value)
DECISION_ACTIONS = {
    PairStatus.CONFIRMED.value: "Paired steps across countries",
    PairStatus.ONLY_REFERENCE.value: "Marked a step as only in one country",
    PairStatus.ONLY_OTHER.value: "Marked a step as only in one country",
    "clear": "Cleared a step pair",
}
DIFFERENCE_ACTIONS = {
    "class": ("Classed country difference", DifferenceStatus.CLASSED.value),
    "keep": ("Kept country difference", DifferenceStatus.KEPT.value),
    "dismiss": ("Dismissed country difference", DifferenceStatus.DISMISSED.value),
    "reopen": ("Reopened country difference", DifferenceStatus.OPEN.value),
}


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _process_of(e: EngagementView) -> str:
    return e.compass.pilot_ref if e.compass else (e.process_name or e.name)


def country_of(e: EngagementView) -> str:
    return e.country or e.name


def same_process(a: EngagementView, b: EngagementView) -> str | None:
    """Why two engagements map the same process (PRD §3.19), or None when they don't."""
    if b.reference_engagement_id == a.id:
        return "started from this map"
    if a.reference_engagement_id == b.id:
        return "this map started from it"
    if a.reference_engagement_id and a.reference_engagement_id == b.reference_engagement_id:
        return "started from the same map"
    if a.compass and b.compass and a.compass.pilot_ref == b.compass.pilot_ref:
        ka, kb = a.compass.key, b.compass.key
        if ka.upper() == kb.upper() or compass_service.same_frame(
            ka, a.compass.cluster_ref, kb, b.compass.cluster_ref
        ):
            return f"same pilot {a.compass.pilot_ref}"
    return None


# --- Reading one side ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Side:
    engagement: EngagementView
    version: VersionView
    steps: list[rules.Step]
    lanes: frozenset[str]
    hidden: list[str]


def _counts(evidence: list[GraphEvidence]) -> tuple[int, int]:
    """(documents, interviews) with a checked passage that speaks to the step."""
    speaking = {
        (e.source_id, e.source_kind) for e in evidence if e.verified and e.stance != "silent"
    }
    interviews = sum(1 for _, k in speaking if k == SourceKind.INTERVIEW_TRANSCRIPT.value)
    return len(speaking) - interviews, interviews


def _side(
    config: AppConfig, session: Session, engagement: EngagementView, version: VersionView
) -> _Side:
    graph = versions_action.build_graph(session, version.id)
    assert graph is not None
    graph = exports.on_the_map(graph)
    roles = {r.id: r.name for r in graph.roles}
    phases = {p.id: p.name for p in graph.phases}
    found: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    if reality_action.enabled(config):  # documented vs done is part of the Reality views
        for item in discrepancies_action.discrepancies_of(session, version).items:
            if item.status == "seen" and item.code:
                for element_id in item.element_ids:
                    found.setdefault(element_id, []).append((item.code, tuple(item.types)))
    steps = []
    for order, e in enumerate(exports.steps(graph), start=1):
        documents, interviews = _counts(list(e.evidence))
        steps.append(
            rules.Step(
                key=e.stable_key,
                code=e.code or "",
                label=e.label,
                kind=e.kind,
                lane=roles.get(e.lane_role_id or "", ""),
                phase=phases.get(e.phase_id or "", ""),
                order=order,
                decider=roles.get(e.decision.decider_role_id or "", ""),
                mechanism=e.decision.mechanism,
                work_type=e.work_type if e.work_type_status == "confirmed" else None,
                work_min=e.time.work_min,
                wait_min=e.time.wait_min,
                provenance=e.provenance,
                documents=documents,
                interviews=interviews,
                discrepancies=tuple(found.get(e.id, [])),
            )
        )
    lanes = frozenset(
        r.name.casefold()
        for r in engagements_repo.list_roles(session, engagement.id)
        if not r.is_system
    )
    hidden = [t.term for t in redaction.name_replacements(session, engagement.id)]
    return _Side(engagement, version, steps, lanes, hidden)


def _side_view(session: Session, side: _Side) -> SideView:
    latest = versions_repo.latest_published(session, side.engagement.id)
    newer = latest["label"] if latest and latest["id"] != side.version.id else None
    return SideView(
        engagement_id=side.engagement.id,
        name=side.engagement.name,
        country=country_of(side.engagement),
        version_id=side.version.id,
        version_label=side.version.label,
        newer_version_label=newer,
    )


def _step_view(s: rules.Step) -> StepView:
    return StepView(
        key=s.key,
        code=s.code,
        label=s.label,
        kind=s.kind,
        lane=s.lane,
        phase=s.phase,
        order=s.order,
    )


# --- The comparison as Eric sees it ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Loaded:
    record: ComparisonRecord
    reference: _Side
    other: _Side
    countries: rules.Countries
    why: str


def _load(config: AppConfig, session: Session, comparison_id: str) -> Result[_Loaded]:
    record = repo.get(session, comparison_id)
    if record is None:
        return Err(ErrorKind.NOT_FOUND, MISSING)
    ref_e = engagements_repo.get(session, record.reference_engagement_id)
    oth_e = engagements_repo.get(session, record.other_engagement_id)
    ref_v = versions_repo.get(session, record.reference_version_id)
    oth_v = versions_repo.get(session, record.other_version_id)
    if ref_e is None or oth_e is None or ref_v is None or oth_v is None:
        return Err(ErrorKind.NOT_FOUND, MISSING)
    reference, other = _side(config, session, ref_e, ref_v), _side(config, session, oth_e, oth_v)
    countries = rules.Countries(
        reference=country_of(ref_e),
        other=country_of(oth_e),
        reference_lanes=reference.lanes,
        other_lanes=other.lanes,
    )
    return Ok(_Loaded(record, reference, other, countries, same_process(oth_e, ref_e) or ""))


def _pairs(
    session: Session, m: _Loaded
) -> tuple[list[PairView], list[tuple[str | None, str | None, str]]]:
    """Eric's decisions, then Claude's suggestions still open, then the rules' proposals."""
    ref_keys = {s.key for s in m.reference.steps}
    oth_keys = {s.key for s in m.other.steps}
    stored = repo.pairs(session, m.record.id)
    decided = [
        p
        for p in stored
        if p.status in DECIDED
        and (p.reference_key is None or p.reference_key in ref_keys)
        and (p.other_key is None or p.other_key in oth_keys)
    ]
    taken_r = {p.reference_key for p in decided if p.reference_key}
    taken_o = {p.other_key for p in decided if p.other_key}
    suggested = [
        p
        for p in stored
        if p.status == PairStatus.SUGGESTED.value
        and p.reference_key in ref_keys - taken_r
        and p.other_key in oth_keys - taken_o
    ]
    taken = taken_r | taken_o | {k for p in suggested for k in (p.reference_key, p.other_key) if k}
    proposals = rules.propose(m.reference.steps, m.other.steps, taken)
    views = [
        PairView(reference_key=p.reference_key, other_key=p.other_key, status=p.status, why=p.why)
        for p in [*decided, *suggested]
    ]
    views += [
        PairView(
            reference_key=p.reference_key,
            other_key=p.other_key,
            status=PairStatus.PROPOSED.value,
            why=p.why,
        )
        for p in proposals
    ]
    return views, [(p.reference_key, p.other_key, p.status) for p in decided]


def _code_key(comparison_id: str, diff_key: str) -> str:
    return f"{comparison_id}|{diff_key}"


def _view(session: Session, m: _Loaded) -> ComparisonView:
    pairs, decided = _pairs(session, m)
    found = rules.differences(m.reference.steps, m.other.steps, decided, m.countries)
    decisions = {d.diff_key: d for d in repo.differences(session, m.record.id)}
    codes = codes_repo.for_engagement(session, m.other.engagement.id, codes_repo.DIFF)
    counts = DifferenceCounts()
    views = []
    for d in found:
        chosen = decisions.get(d.key)
        status = chosen.status if chosen else DifferenceStatus.OPEN.value
        setattr(counts, status, getattr(counts, status) + 1)
        views.append(
            DifferenceView(
                key=d.key,
                kind=d.kind,
                topic=d.topic,
                title=d.title,
                reference_value=d.reference_value,
                other_value=d.other_value,
                figure=d.figure,
                reference_key=d.reference_key,
                other_key=d.other_key,
                status=status,
                code=codes.get(_code_key(m.record.id, d.key)),
                reason_class=chosen.reason_class if chosen else None,
                reason_note=chosen.reason_note if chosen else "",
                note=chosen.note if chosen else "",
                grade=GradeView(
                    grade=(chosen.grade if chosen and chosen.grade else d.suggested_grade),
                    suggested=d.suggested_grade,
                    chosen_by_owner=bool(chosen and chosen.grade),
                    rules_version=rules.COUNTRY_RULES_VERSION,
                ),
                grade_reason=d.grade_reason,
            )
        )
    current = {d.key for d in found}
    gone = [
        DifferenceView(
            key=d.diff_key,
            kind=d.diff_key.split("|", 1)[0],
            topic="",
            title=d.title,
            reference_value="",
            other_value="",
            figure="",
            reference_key=None,
            other_key=None,
            status=d.status,
            code=codes.get(_code_key(m.record.id, d.diff_key)),
            reason_class=d.reason_class,
            reason_note=d.reason_note,
            note=d.note,
            grade=GradeView(
                grade=d.grade or grade_rules.HYPOTHESIS,
                suggested=grade_rules.HYPOTHESIS,
                chosen_by_owner=bool(d.grade),
                rules_version=rules.COUNTRY_RULES_VERSION,
            ),
            grade_reason="",
        )
        for d in decisions.values()
        if d.diff_key not in current and d.status != DifferenceStatus.OPEN.value
    ]
    job = jobs_repo.get(session, m.record.suggest_job_id) if m.record.suggest_job_id else None
    return ComparisonView(
        id=m.record.id,
        rules_version=rules.COUNTRY_RULES_VERSION,
        reference=_side_view(session, m.reference),
        other=_side_view(session, m.other),
        same_process=m.why,
        steps={
            "reference": [_step_view(s) for s in m.reference.steps],
            "other": [_step_view(s) for s in m.other.steps],
        },
        pairs=pairs,
        differences=views,
        no_longer_found=gone,
        counts=counts,
        suggest_job=SuggestJob(job_id=job.id, status=job.status) if job else None,
    )


def view_of(config: AppConfig, session: Session, comparison_id: str) -> Result[ComparisonView]:
    match _load(config, session, comparison_id):
        case Err() as err:
            return err
        case Ok(value=m):
            return Ok(_view(session, m))


def get_comparison(
    config: AppConfig, sessions: Sessions, comparison_id: str
) -> Result[ComparisonView]:
    with session_scope(sessions) as session:
        return view_of(config, session, comparison_id)


# --- Choosing what to compare -----------------------------------------------------------------


def candidates(sessions: Sessions, engagement_id: str) -> Result[list[Candidate]]:
    """The engagements mapping the same process as this one, in another country."""
    with session_scope(sessions) as session:
        here = engagements_repo.get(session, engagement_id)
        if here is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        out = []
        for other in engagements_repo.all_views(session):
            why = same_process(here, other) if other.id != engagement_id else None
            if why is None:
                continue
            latest = versions_repo.latest_published(session, other.id)
            out.append(
                Candidate(
                    engagement_id=other.id,
                    name=other.name,
                    country=other.country,
                    process_name=other.process_name,
                    why=why,
                    published_version_id=latest["id"] if latest else None,
                    published_label=latest["label"] if latest else None,
                )
            )
        return Ok(out)


def list_comparisons(
    config: AppConfig, sessions: Sessions, engagement_id: str
) -> Result[list[ComparisonSummary]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        out = []
        for record in repo.for_engagement(session, engagement_id):
            match _load(config, session, record.id):
                case Ok(value=m):
                    view = _view(session, m)
                    out.append(
                        ComparisonSummary(
                            id=view.id,
                            reference=view.reference,
                            other=view.other,
                            differences=view.counts,
                        )
                    )
                case Err():
                    continue
        return Ok(out)


def _published(session: Session, e: EngagementView, version_id: str | None) -> Result[VersionView]:
    if version_id is None:
        latest = versions_repo.latest_published(session, e.id)
        if latest is None:
            return Err(ErrorKind.CONFLICT, NO_PUBLISHED.format(name=e.name))
        version_id = str(latest["id"])
    version = versions_repo.get(session, version_id)
    if version is None:
        return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
    if version.engagement_id != e.id:
        return _invalid("version_id", NOT_ITS_VERSION.format(name=e.name))
    if version.state not in PUBLISHED:
        return Err(ErrorKind.CONFLICT, A_DRAFT.format(label=version.label, name=e.name))
    return Ok(version)


def start_comparison(
    config: AppConfig, sessions: Sessions, body: ComparisonCreate
) -> Result[tuple[ComparisonView, bool]]:
    """The comparison of two engagements (created, True; or the existing one, False)."""
    if body.reference_engagement_id == body.other_engagement_id:
        return _invalid("other_engagement_id", SAME_ENGAGEMENT)
    with session_scope(sessions) as session:
        reference = engagements_repo.get(session, body.reference_engagement_id)
        other = engagements_repo.get(session, body.other_engagement_id)
        if reference is None or other is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if same_process(other, reference) is None:
            return Err(
                ErrorKind.CONFLICT, DIFFERENT.format(a=_process_of(reference), b=_process_of(other))
            )
        versions = []
        for e, vid in ((reference, body.reference_version_id), (other, body.other_version_id)):
            match _published(session, e, vid):
                case Err() as err:
                    return err
                case Ok(value=version):
                    versions.append(version)
        existing = repo.find(session, reference.id, other.id)
        if existing is not None:
            match view_of(config, session, existing.id):
                case Err() as err:
                    return err
                case Ok(value=view):
                    return Ok((view, False))
        record = repo.create(
            session,
            {
                "reference_engagement_id": reference.id,
                "other_engagement_id": other.id,
                "reference_version_id": versions[0].id,
                "other_version_id": versions[1].id,
            },
        )
        audit.record(
            session,
            actor=actor_name(config),
            action="Started country comparison",
            target_type="comparison",
            target_id=record.id,
            engagement_id=other.id,
            after={
                "reference": reference.name,
                "other": other.name,
                "reference_version": versions[0].label,
                "other_version": versions[1].label,
            },
        )
        match view_of(config, session, record.id):
            case Err() as err:
                return err
            case Ok(value=view):
                return Ok((view, True))


# --- Eric's decisions on pairs ----------------------------------------------------------------


def set_pair(
    config: AppConfig, sessions: Sessions, comparison_id: str, body: PairDecision
) -> Result[ComparisonView]:
    if body.decision not in DECISION_ACTIONS:
        return _invalid("decision", BAD_DECISION)
    with session_scope(sessions) as session:
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        ref_keys = {s.key for s in m.reference.steps}
        oth_keys = {s.key for s in m.other.steps}
        r, o = body.reference_key, body.other_key
        if body.decision == PairStatus.CONFIRMED.value and not (r and o):
            return _invalid("reference_key", CHOOSE_STEPS)
        if body.decision == PairStatus.ONLY_REFERENCE.value:
            o = None
            if not r:
                return _invalid("reference_key", CHOOSE_STEPS)
        if body.decision == PairStatus.ONLY_OTHER.value:
            r = None
            if not o:
                return _invalid("other_key", CHOOSE_STEPS)
        if body.decision == "clear" and not (r or o):
            return _invalid("reference_key", CHOOSE_STEPS)
        if (r and r not in ref_keys) or (o and o not in oth_keys):
            return _invalid("reference_key" if r and r not in ref_keys else "other_key", NOT_ON_MAP)
        stale = [
            p.id
            for p in repo.pairs(session, comparison_id)
            if (r and p.reference_key == r) or (o and p.other_key == o)
        ]
        repo.delete_pairs(session, stale)
        if body.decision != "clear":
            repo.add_pair(session, comparison_id, r, o, body.decision)
        audit.record(
            session,
            actor=actor_name(config),
            action=DECISION_ACTIONS[body.decision],
            target_type="comparison",
            target_id=comparison_id,
            engagement_id=m.other.engagement.id,
            after={"reference_key": r, "other_key": o, "decision": body.decision},
        )
        return view_of(config, session, comparison_id)


def refresh(config: AppConfig, sessions: Sessions, comparison_id: str) -> Result[ComparisonView]:
    """Move to each side's latest published version, keeping Eric's decisions by stable key."""
    with session_scope(sessions) as session:
        record = repo.get(session, comparison_id)
        if record is None:
            return Err(ErrorKind.NOT_FOUND, MISSING)
        fields = {}
        for column, engagement_id in (
            ("reference_version_id", record.reference_engagement_id),
            ("other_version_id", record.other_engagement_id),
        ):
            latest = versions_repo.latest_published(session, engagement_id)
            if latest is not None:
                fields[column] = str(latest["id"])
        repo.update(session, comparison_id, fields)
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        ref_keys = {s.key for s in m.reference.steps}
        oth_keys = {s.key for s in m.other.steps}
        gone = [
            p.id
            for p in repo.pairs(session, comparison_id)
            if (p.reference_key and p.reference_key not in ref_keys)
            or (p.other_key and p.other_key not in oth_keys)
        ]
        repo.delete_pairs(session, gone)
        audit.record(
            session,
            actor=actor_name(config),
            action="Refreshed country comparison",
            target_type="comparison",
            target_id=comparison_id,
            engagement_id=m.other.engagement.id,
            after={
                "reference_version": m.reference.version.label,
                "other_version": m.other.version.label,
                "dropped_pairs": len(gone),
            },
        )
        return view_of(config, session, comparison_id)


# --- Eric's decisions on differences ----------------------------------------------------------


def _line(field: str, value: str, hidden: list[str], what: str) -> Result[str]:
    text = value.strip()
    if len(text) > MAX_LINE or "\n" in text:
        return _invalid(field, BAD_LINE)
    if grounding.scan_redaction_terms(text, hidden):
        return _invalid(field, HIDDEN.format(what=what))
    return Ok(text)


def decide(
    config: AppConfig,
    sessions: Sessions,
    comparison_id: str,
    diff_key: str,
    body: DifferenceDecision,
) -> Result[DifferenceView]:
    """Class, keep, dismiss or reopen one difference. The first class or keep gives its Vn."""
    if body.action not in DIFFERENCE_ACTIONS:
        return _invalid("action", BAD_ACTION)
    if body.grade is not None and body.grade not in grade_rules.GRADES:
        return _invalid("grade", BAD_GRADE)
    with session_scope(sessions) as session:
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        current = next((d for d in _view(session, m).differences if d.key == diff_key), None)
        if current is None:
            return Err(ErrorKind.NOT_FOUND, NO_DIFFERENCE)
        hidden = [*m.reference.hidden, *m.other.hidden]
        match _line("reason_note", body.reason_note, hidden, "The reason"):
            case Err() as err:
                return err
            case Ok(value=reason_note):
                pass
        match _line("note", body.note, hidden, "The note"):
            case Err() as err:
                return err
            case Ok(value=note):
                pass
        action, status = DIFFERENCE_ACTIONS[body.action]
        fields: dict[str, object] = {"status": status, "title": current.title}
        if body.action == "class":
            if body.reason_class not in {r.value for r in ReasonClass}:
                return _invalid("reason_class", BAD_REASON)
            if body.reason_class != ReasonClass.UNKNOWN.value and not reason_note:
                return _invalid("reason_note", NEEDS_REASON)
            fields |= {
                "reason_class": body.reason_class,
                "reason_note": reason_note,
                "grade": body.grade,
                "note": "",
            }
        elif body.action == "keep":
            fields |= {
                "reason_class": None,
                "reason_note": reason_note,
                "grade": body.grade,
                "note": "",
            }
        elif body.action == "dismiss":
            if not note:
                return _invalid("note", NEEDS_NOTE)
            fields |= {"note": note}
        else:
            fields |= {"reason_class": None, "reason_note": "", "grade": None, "note": ""}
        before = {
            "status": current.status,
            "reason_class": current.reason_class,
            "reason_note": current.reason_note,
            "note": current.note,
        }
        repo.save_difference(session, comparison_id, diff_key, fields)
        if body.action in ("class", "keep"):  # the code, once, never reused (DECISIONS 98)
            codes_repo.ensure(
                session,
                m.other.engagement.id,
                codes_repo.DIFF,
                [_code_key(comparison_id, diff_key)],
            )
        audit.record(
            session,
            actor=actor_name(config),
            action=action,
            target_type="comparison",
            target_id=comparison_id,
            engagement_id=m.other.engagement.id,
            before=before,
            after={"key": diff_key, **fields},
        )
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=fresh):
                pass
        updated = next(d for d in _view(session, fresh).differences if d.key == diff_key)
        return Ok(updated)


# --- Claude's suggestions (CC_match) ---------------------------------------------------------


def _unpaired(session: Session, m: _Loaded) -> tuple[list[rules.Step], list[rules.Step]]:
    pairs, _ = _pairs(session, m)
    taken = {k for p in pairs for k in (p.reference_key, p.other_key) if k}
    return (
        [s for s in m.reference.steps if s.key not in taken],
        [s for s in m.other.steps if s.key not in taken],
    )


def start_suggest(
    config: AppConfig, sessions: Sessions, comparison_id: str, enqueue: Enqueue
) -> Result[SuggestStarted]:
    with session_scope(sessions) as session:
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        if comparison_id in jobs_repo.unfinished_targets(session, MATCH_JOB):
            return Err(ErrorKind.CONFLICT, BUSY)
        left, right = _unpaired(session, m)
        if not left or not right:
            return Err(ErrorKind.CONFLICT, NOTHING_TO_SUGGEST)
        job = jobs_repo.create(
            session,
            engagement_id=m.other.engagement.id,
            job_type=MATCH_JOB,
            target_id=comparison_id,
        )
        repo.update(session, comparison_id, {"suggest_job_id": job.id})
    enqueue(job.id)
    return Ok(SuggestStarted(job_id=job.id, comparison_id=comparison_id))


_KEY = re.compile(r"\S+")


def check_suggestions(
    found: list[cc_match.Suggestion], left: set[str], right: set[str]
) -> tuple[list[cc_match.Suggestion], int]:
    """Only pairs of existing, unpaired keys, each key once; the rest are counted, not kept."""
    kept, used = [], set()
    for s in found:
        ok = (
            s.reference_key in left
            and s.other_key in right
            and s.reference_key not in used
            and s.other_key not in used
            and _KEY.fullmatch(s.reference_key)
        )
        if ok:
            kept.append(s)
            used |= {s.reference_key, s.other_key}
    return kept, len(found) - len(kept)


def run_suggest(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """The suggestion job: Claude's pairs, checked, stored as suggestions for Eric."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        comparison_id = (job.target_id or "") if job else ""
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        left, right = _unpaired(session, m)
    if not left or not right:
        return Ok(NOTHING_TO_SUGGEST)
    match ai_context(config):
        case Err() as err:
            return err
        case Ok(value=ctx):
            pass
    match cc_match.suggest(sessions, ctx, left, right, job_id):
        case Err() as err:
            return err
        case Ok(value=found):
            pass
    kept, left_out = check_suggestions(found, {s.key for s in left}, {s.key for s in right})
    with session_scope(sessions) as session:
        old = [
            p.id
            for p in repo.pairs(session, comparison_id)
            if p.status == PairStatus.SUGGESTED.value
        ]
        repo.delete_pairs(session, old)
        for s in kept:
            repo.add_pair(
                session,
                comparison_id,
                s.reference_key,
                s.other_key,
                PairStatus.SUGGESTED.value,
                s.reason[:MAX_LINE],
            )
    message = SUGGESTED.format(n=len(kept), pairs="pair" if len(kept) == 1 else "pairs")
    if left_out:
        message += LEFT_OUT.format(
            n=left_out,
            suggestions="suggestion was" if left_out == 1 else "suggestions were",
            it="it" if left_out == 1 else "they",
        )
    return Ok(message)


# --- Printable pages (PRD §3.19) --------------------------------------------------------------

LEAK = (
    "The pages would have held a name on a list of names to hide, so nothing was downloaded. "
    "Check both engagements' lists of names to hide and the wording of the reasons, then try again."
)


def export_pages(
    config: AppConfig, sessions: Sessions, comparison_id: str, layout: str
) -> Result[ExportFile]:
    """The summary, Who decides, How the work differs and Only in one country, as one HTML file."""
    if layout not in export_comparison.LAYOUTS:
        return _invalid("layout", reality_pack.BAD_LAYOUT)
    with session_scope(sessions) as session:
        match _load(config, session, comparison_id):
            case Err() as err:
                return err
            case Ok(value=m):
                pass
        view = _view(session, m)
        process = m.other.engagement.process_name or m.other.engagement.name
        tokens, fonts = quality_action.html_assets()
        content = export_comparison.render(
            view,
            layout,
            process=process,
            tokens=tokens,
            fonts=fonts,
            reality_css=reality_pack.reality_css(),
        )
        hidden = [*m.reference.hidden, *m.other.hidden]
        if compass_return.leaks(content, hidden, compass_return.SECRET_MARKERS):
            return Err(ErrorKind.CONFLICT, LEAK)
        audit.record(
            session,
            actor=actor_name(config),
            action="Exported country comparison",
            target_type="comparison",
            target_id=comparison_id,
            engagement_id=m.other.engagement.id,
            after={"layout": layout},
        )
        name = (
            f"{publish.slug(process)}-{publish.slug(view.other.country)}-vs-"
            f"{publish.slug(view.reference.country)}-{layout}.html"
        )
        return Ok(ExportFile(filename=name, media_type=reality_pack.MEDIA, content=content))


# --- Findings for the Compass (PRD §3.19) -----------------------------------------------------


def _rests(country: str, step: rules.Step | None) -> str:
    if step is None:
        return f"{country} has no such step"
    parts = (
        [f"{step.interviews} interview{'s' if step.interviews != 1 else ''}"]
        if step.interviews
        else []
    )
    parts += (
        [f"{step.documents} document{'s' if step.documents != 1 else ''}"] if step.documents else []
    )
    return f"{country}'s step rests on {' and '.join(parts) or 'no checked source'}"


def variations_for(
    config: AppConfig, session: Session, engagement_id: str, version_id: str
) -> tuple[list[compass_return.Variation], list[str]]:
    """The classed or kept differences of the comparisons where this engagement, at this version,
    is the other country (each difference reported once, by the country compared), and the
    reference engagements' names to hide, for the leaks check."""
    out: list[compass_return.Variation] = []
    hidden: list[str] = []
    for record in repo.as_other(session, engagement_id, version_id):
        match _load(config, session, record.id):
            case Err():
                continue
            case Ok(value=m):
                pass
        hidden += m.reference.hidden
        ref_steps = {s.key: s for s in m.reference.steps}
        oth_steps = {s.key: s for s in m.other.steps}
        process = _process_of(m.other.engagement)
        for d in _view(session, m).differences:
            if d.status not in (DifferenceStatus.CLASSED.value, DifferenceStatus.KEPT.value):
                continue
            if not d.code:
                continue
            here = oth_steps.get(d.other_key or "")
            there = ref_steps.get(d.reference_key or "")
            note = (
                f"Compared between the two published maps of {process}; "
                f"{_rests(m.countries.other, here)}; {_rests(m.countries.reference, there)}."
            )
            out.append(
                compass_return.Variation(
                    code=d.code,
                    kind=d.kind,
                    title=d.title,
                    topic=d.topic,
                    step_code=here.code if here else "",
                    step_label=here.label if here else (there.label if there else ""),
                    reason_class=d.reason_class
                    if d.status == DifferenceStatus.CLASSED.value
                    else None,
                    reason_note=d.reason_note,
                    grade=d.grade.grade,
                    figure=d.figure,
                    country=m.countries.other,
                    compared_with=m.countries.reference,
                    source_note=note,
                )
            )
    out.sort(key=lambda v: int(v.code[1:]) if v.code[1:].isdigit() else 0)
    return out, hidden
