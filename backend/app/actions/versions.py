"""Versions and their graph (PRD §3.5 versions, §3.6 graph JSON).

`build_graph` assembles the graph of one version from the stored map: every element with its time,
decision rights, handoffs, RACI, constraints, AI flag and evidence. Every source the draft was made
from appears in an element's evidence; a source with nothing to say about the element is shown as
`silent` with no passage (constraint 4). Names are hidden in every text (G10); verbatim quotes and
images are never part of the graph.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction, view_translation
from app.db import session_scope
from app.domain.enums import EdgeKind, ElementKind, ReviewStatus, Stance, VersionState
from app.domain.graph import (
    AlignmentRow,
    AnswerQuote,
    CycleTime,
    EdgeRecord,
    ElementDetail,
    ElementRecord,
    EvidenceCard,
    Graph,
    GraphAiFlag,
    GraphConstraint,
    GraphDecision,
    GraphEdge,
    GraphElement,
    GraphEvidence,
    GraphHandoff,
    GraphPhase,
    GraphProcess,
    GraphRaci,
    GraphRole,
    GraphTime,
    GraphVersion,
    LintReport,
    RaciDetail,
    RaciSource,
)
from app.domain.interview import QuestionBank
from app.domain.layout import Layout
from app.domain.models import ClaimRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import View
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import gap as gap_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import (
    alignment,
    interview_templates,
    layout,
    lint,
    parsing,
    translation,
    views,
)

Sessions = sessionmaker[Session]

VERSION_MISSING = "That version doesn't exist."
FROZEN = {VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value}
ELEMENT_MISSING = "That step doesn't exist."
# Edges that leave the main path: exception routes and loops back.
OFF_MAIN_PATH = {
    EdgeKind.NO.value,
    EdgeKind.REJECT.value,
    EdgeKind.REWORK.value,
    EdgeKind.EXCEPTION.value,
}
TIMED_KINDS = {ElementKind.ACTIVITY.value, ElementKind.APPROVAL.value}
STRUCTURAL = {ElementKind.START.value, ElementKind.END.value}


def main_path(elements: list[ElementRecord], edges: list[EdgeRecord]) -> list[ElementRecord]:
    """The route from start to end that follows no exception or loop-back edge.

    At each step the first main-path edge (in stored order) is taken; a step already visited
    ends the walk, so a cycle can never loop forever.
    """
    by_id = {e.id: e for e in elements if e.review_status != ReviewStatus.REJECTED.value}
    start = next((e for e in by_id.values() if e.kind == ElementKind.START.value), None)
    path: list[ElementRecord] = []
    seen: set[str] = set()
    current = start
    while current is not None and current.id not in seen:
        path.append(current)
        seen.add(current.id)
        nxt = next(
            (
                by_id[edge.to_element_id]
                for edge in edges
                if edge.from_element_id == current.id
                and edge.kind not in OFF_MAIN_PATH
                and edge.to_element_id in by_id
            ),
            None,
        )
        current = nxt
    return path


def cycle_time(elements: list[ElementRecord], edges: list[EdgeRecord]) -> CycleTime:
    """Work and elapsed minutes along the main path; activities and approvals without any time
    are counted as incomplete (decisions carry no time of their own)."""
    path = main_path(elements, edges)
    work = sum(e.work_min or 0 for e in path)
    wait = sum(e.wait_min or 0 for e in path)
    incomplete = sum(
        1 for e in path if e.kind in TIMED_KINDS and e.work_min is None and e.wait_min is None
    )
    return CycleTime(elapsed_min=work + wait, work_min=work, incomplete_steps=incomplete)


def combined_lines(edges: list[EdgeRecord]) -> list[EdgeRecord]:
    """The lines of the one map that shows both views' steps: without the lines the translation
    added for a single view where the other view's steps are left out (provenance I, PRD §3.12.10;
    each view is drawn on its own from V1, 2026-10-01)."""
    return [e for e in edges if not views.added_for_one_view(e.provenance, e.view_membership)]


def build_graph(
    session: Session, version_id: str, *, every_line: bool = False, view: View | None = None
) -> Graph | None:
    """The version's graph. Without `every_line` the lines are the combined map's (what the
    layout, lint, quality card, exports and leadership read); the graph endpoint returns every
    line with its view membership. With a view, only that view's steps and lines, and the cycle
    time along that view's main path (§3.12.11)."""
    version = versions_repo.get(session, version_id)
    if version is None:
        return None
    engagement = engagements_repo.get(session, version.engagement_id)
    if engagement is None:
        return None
    terms = redaction.name_replacements(session, engagement.id)

    def hide(text: str) -> str:
        return redaction.hide(text, terms)

    roles = engagements_repo.list_roles(session, engagement.id)
    phases = map_repo.phases(session, version_id)
    elements = map_repo.elements(session, version_id)
    edges = map_repo.edges(session, version_id)
    if view is not None:
        elements = [e for e in elements if views.in_view(e.view_membership, view)]
        shown = {e.id for e in elements}
        edges = [
            e
            for e in edges
            if views.in_view(e.view_membership, view)
            and e.from_element_id in shown
            and e.to_element_id in shown
        ]
    elif not every_line:
        edges = combined_lines(edges)
    raci = map_repo.raci(session, version_id)
    constraints = map_repo.constraints(session, version_id)
    flags = map_repo.ai_flags(session, version_id)
    passages = map_repo.evidence(session, version_id)
    claims_of = map_repo.element_claims(session, version_id)
    claim_records = claims_repo.by_ids(session, [c for ids in claims_of.values() for c in ids])
    drafted_from = [
        s
        for sid in map_repo.version_source_ids(session, version_id)
        if (s := sources_repo.get(session, sid)) is not None
    ]

    def evidence_for(element_id: str, kind: str) -> list[GraphEvidence]:
        if kind in STRUCTURAL:
            return []  # start and end come from the scope card, not from the sources
        linked = [p for p in passages if p.evidence.element_id == element_id]
        out = [
            GraphEvidence(
                segment_id=p.evidence.segment_id,
                source_id=p.source_id,
                source_kind=p.evidence.source_kind,
                stance=p.evidence.stance,
                anchor=parsing.segment_anchor(
                    fmt=p.source_format,
                    seq=p.seq,
                    page=p.page,
                    section=p.section,
                    text=p.text,
                    start_ms=p.start_ms,
                ),
                verified=p.evidence.verified,
                note=hide(p.evidence.note),
            )
            for p in linked
        ]
        speaking = {p.source_id for p in linked}
        out += [
            GraphEvidence(
                segment_id=None,
                source_id=s.id,
                source_kind=s.kind,
                stance=Stance.SILENT.value,
                anchor="",
                verified=False,
            )
            for s in drafted_from
            if s.id not in speaking
        ]
        return out

    # Process order for reading: start first, end last, the steps as the pipeline made them.
    rank = {ElementKind.START.value: 0, ElementKind.END.value: 2}
    elements = sorted(elements, key=lambda e: rank.get(e.kind, 1))
    graph_elements = []
    for e in elements:
        flag = next((f for f in flags if f.element_id == e.id), None)
        accounts = translation.account_summary(
            claim_records[c].account_type for c in claims_of.get(e.id, []) if c in claim_records
        )
        graph_elements.append(
            GraphElement(
                id=e.id,
                stable_key=e.stable_key,
                kind=e.kind,
                label=hide(e.label),
                lane_role_id=e.lane_role_id,
                phase_id=e.phase_id,
                time=GraphTime(work_min=e.work_min, wait_min=e.wait_min, text=e.duration_text),
                complexity=e.complexity,
                kpi=hide(e.kpi),
                decision=GraphDecision(
                    mechanism=e.decision_mechanism,
                    decider_role_id=e.decider_role_id,
                    rule_or_threshold=hide(e.rule_or_threshold),
                    escalation=hide(e.escalation),
                ),
                handoff=GraphHandoff(in_=hide(e.handoff_in), out=hide(e.handoff_out)),
                raci=[
                    GraphRaci(role_id=r.role_id, letter=r.letter, contested=r.contested)
                    for r in raci
                    if r.element_id == e.id
                ],
                provenance=e.provenance,
                r_reference=e.r_reference,
                source_state=e.source_state,
                divergence_types=list(e.divergence_types),
                constraints=[
                    GraphConstraint(
                        text=hide(c.text),
                        provenance=c.provenance,
                        cause_type=c.cause_type,
                        is_key=c.is_key,
                    )
                    for c in constraints
                    if c.element_id == e.id
                ],
                k_risk=hide(e.k_risk),
                ai_flag=GraphAiFlag(
                    component=flag.component,
                    input=hide(flag.input),
                    output=hide(flag.output),
                    handoff=hide(flag.handoff),
                    basis=flag.basis,
                )
                if flag
                else None,
                evidence=evidence_for(e.id, e.kind),
                confidence=e.confidence,
                confidence_breakdown=list(e.confidence_breakdown),
                needs_check=e.needs_check,
                review_status=e.review_status,
                account_summary=accounts,
                practice_described=translation.practice_described(accounts),
                variants=e.variants,
                view_membership=e.view_membership,
            )
        )

    return Graph(
        version=GraphVersion(id=version.id, label=version.label, state=version.state),
        process=GraphProcess(
            name=hide(engagement.process_name or engagement.name),
            trigger=hide(engagement.trigger),
            end_point=hide(engagement.end_point),
            kpi=hide(engagement.process_kpi),
            cycle_time=cycle_time(elements, edges if view else combined_lines(edges)),
        ),
        roles=[
            GraphRole(id=r.id, name=r.name, is_system=r.is_system, lane_order=r.lane_order)
            for r in roles
        ],
        phases=[
            GraphPhase(id=p.id, name=hide(p.name), time_window=p.time_window, order=p.sort_order)
            for p in phases
        ],
        elements=graph_elements,
        edges=[
            GraphEdge(
                id=e.id,
                from_=e.from_element_id,
                to=e.to_element_id,
                kind=e.kind,
                label=hide(e.label),
                sequence_basis=e.sequence_basis,
                view_membership=e.view_membership,
                information_payload=hide(e.information_payload)
                if e.information_payload is not None
                else None,
                typical=e.typical,
                provenance=e.provenance,
            )
            for e in edges
        ],
    )


def get_graph(sessions: Sessions, version_id: str, view: View | None = None) -> Result[Graph]:
    """Every line with its view membership; with a view, only that view's steps and lines."""
    with session_scope(sessions) as session:
        graph = build_graph(session, version_id, every_line=True, view=view)
    return Ok(graph) if graph else Err(ErrorKind.NOT_FOUND, VERSION_MISSING)


def get_alignment_matrix(sessions: Sessions, version_id: str) -> Result[list[AlignmentRow]]:
    """How each kind of source stands on each step (API_CONTRACT → Views; PRD §5.4 Matrix)."""
    with session_scope(sessions) as session:
        graph = build_graph(session, version_id)
    if graph is None:
        return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
    return Ok(alignment.alignment_matrix(graph))


def get_layout(
    sessions: Sessions, version_id: str, view: View | None = None, show_other: bool = False
) -> Result[Layout]:
    """Where the UI draws the version's map (PRD §3.9): the combined map, or one view (§3.12.11),
    optionally with the other view's steps ghosted."""
    with session_scope(sessions) as session:
        graph = build_graph(session, version_id, every_line=True)
    if graph is None:
        return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
    if view is None:
        return Ok(layout.compute_layout(views.combined(graph)))
    if not show_other:
        drawn = layout.compute_layout(views.view_graph(graph, view))
        return Ok(drawn.model_copy(update={"view": view}))
    drawn = layout.compute_layout(views.with_other_view(graph, view))
    return Ok(views.mark_ghosts(drawn, graph, view))


def lint_graph(every: Graph) -> LintReport:
    """The lint rules on the map as one (with its layout), then each view's flow checks
    (§3.12.11), from the graph with every line. Used for the stored report, the quality card and
    publishing alike."""
    graph = views.combined(every)
    whole = lint.run_lint(graph, layout.compute_layout(graph))
    per_view = lint.run_view_checks(every)
    return LintReport(
        failures=whole.failures + per_view.failures, warnings=whole.warnings + per_view.warnings
    )


def lint_for(session: Session, version_id: str) -> LintReport | None:
    every = build_graph(session, version_id, every_line=True)
    return lint_graph(every) if every is not None else None


def lint_version(sessions: Sessions, version_id: str, *, ask: bool = True) -> Result[LintReport]:
    """Bring the views up to date after a change to the map (deterministic, no AI: new steps and
    lines get their view membership, and each view the lines it needs, with their questions),
    then run the lint rules and store the report on the version."""
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        # A published version never changes (constraint 8); only drafts are brought up to date.
        if version is not None and version.state not in FROZEN:
            view_translation.update_views(session, version_id)
            if ask:  # the draft asks after S5, so step questions come first
                view_translation.add_questions(session, version_id)
        report = lint_for(session, version_id)
        if report is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        versions_repo.set_lint_report(session, version_id, report.model_dump(mode="json"))
    return Ok(report)


def get_lint(sessions: Sessions, version_id: str) -> Result[LintReport]:
    """The lint report stored with the version, or a fresh one if none was stored."""
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        stored = versions_repo.lint_report(session, version_id)
    if stored is not None:
        return Ok(LintReport.model_validate(stored))
    return lint_version(sessions, version_id)


def _answer(
    record: ClaimRecord,
    where: dict[str, tuple[str, str | None]],
    bank: QuestionBank | None,
    hide: Callable[[str], str],
) -> AnswerQuote:
    first = record.segment_ids[0] if record.segment_ids else None
    anchor, question_id = where.get(first or "", ("", None))
    question = ""
    if bank is not None and question_id and any(q.id == question_id for q in bank.questions):
        question = bank.question(question_id).wording
    return AnswerQuote(
        quote=hide(record.quote),
        account_type=record.account_type or "unclear",
        account_cue=hide(str(record.payload.get("account_cue", ""))),
        stated_reason=hide(str(record.payload.get("stated_reason", ""))),
        variation_condition=hide(str(record.payload.get("variation_condition", ""))),
        source_id=record.source_id,
        segment_id=first,
        anchor=anchor,
        question_id=question_id,
        question=question,
    )


def get_element(sessions: Sessions, element_id: str) -> Result[ElementDetail]:
    """One step as the detail panel shows it: the graph element with role, lane and phase names,
    each evidence card's source name and quote, and the passages behind each RACI entry. Names
    are hidden everywhere (G10); quotes stay in the app and never reach an export."""
    with session_scope(sessions) as session:
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        graph = build_graph(session, version.id) if version else None
        element = next((e for e in graph.elements if e.id == element_id), None) if graph else None
        if version is None or graph is None or element is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        terms = redaction.name_replacements(session, version.engagement_id)
        passages = map_repo.evidence(session, version.id)
        raci = [r for r in map_repo.raci(session, version.id) if r.element_id == element_id]
        sources = sources_repo.list_for_engagement(session, version.engagement_id)
        names = {s.id: s.filename for s in sources}
        images = map_repo.image_count(session, element_id)
        found = gap_repo.step_findings(session, version.engagement_id, element.stable_key)
        claim_ids = map_repo.element_claims(session, version.id).get(element_id, [])
        records = claims_repo.by_ids(session, claim_ids)
        interview = [records[c] for c in claim_ids if c in records and records[c].account_type]
        rows = sources_repo.segment_rows(
            session, [r.segment_ids[0] for r in interview if r.segment_ids]
        )
        # The first passage each answer cites: its anchor and the guide question it answers.
        where = {
            sid: (
                parsing.segment_anchor(fmt=fmt, seq=seg.seq, page=seg.page, section=seg.section,
                                       text=seg.text, start_ms=seg.start_ms),
                seg.question_id,
            )
            for sid, (seg, fmt) in rows.items()
        }  # fmt: skip

    def hide(text: str) -> str:
        return redaction.hide(text, terms)

    loaded = interview_templates.load_bank()
    bank = loaded.value if isinstance(loaded, Ok) else None
    roles = {r.id: r.name for r in graph.roles}
    phases = {p.id: p.name for p in graph.phases}
    linked = [p for p in passages if p.evidence.element_id == element_id]
    # build_graph lists the linked passages first, in this same order, then the silent sources.
    cards = [
        EvidenceCard(
            segment_id=ev.segment_id,
            source_id=ev.source_id,
            source_name=hide(names.get(ev.source_id, "")),
            source_kind=ev.source_kind,
            stance=ev.stance,
            anchor=ev.anchor,
            verified=ev.verified,
            quote=hide(linked[i].evidence.quote) if i < len(linked) else "",
            note=ev.note,
        )
        for i, ev in enumerate(element.evidence)
    ]

    def sources_of(raci_id: str) -> list[RaciSource]:
        return [
            RaciSource(
                source_name=hide(p.source_name),
                source_kind=p.evidence.source_kind,
                anchor=parsing.segment_anchor(fmt=p.source_format, seq=p.seq, page=p.page,
                                              section=p.section, text=p.text,
                                              start_ms=p.start_ms),
            )
            for p in passages
            if p.evidence.raci_id == raci_id
        ]  # fmt: skip

    fields = element.model_dump(by_alias=False, exclude={"evidence", "raci"})
    return Ok(
        ElementDetail(
            **fields,
            version_id=version.id,
            lane_role_name=roles.get(element.lane_role_id or "", ""),
            phase_name=phases.get(element.phase_id or "", ""),
            decider_role_name=roles.get(element.decision.decider_role_id or "", ""),
            raci=[
                RaciDetail(
                    role_id=r.role_id,
                    role_name=roles.get(r.role_id, ""),
                    letter=r.letter,
                    contested=r.contested,
                    sources=sources_of(r.id),
                )
                for r in raci
            ],
            evidence=cards,
            image_count=images,
            answers=[_answer(r, where, bank, hide) for r in interview],
            gap_findings=[
                {
                    "id": f.id,
                    "analysis_id": a.id,
                    "mode": a.mode,
                    "title": hide(f.title),
                    "severity": f.severity,
                    "disposition": f.disposition,
                }
                for a, f in found
            ],
        )
    )
