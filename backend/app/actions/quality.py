"""The quality card and the exports of a version (PRD §7.2, §7.3; phase P7).

`export_input` gathers what the renderers need (graph, source registry, validator, open
questions), `render_exports` writes every format, and `card_for` works out the quality card from
the map, its lint report and those rendered exports (Q7-Q9 read the real output). A draft's card
is worked out afresh each time and stored with it; a published version keeps the card it was
published with.
"""

from __future__ import annotations

import json
from functools import cache

from sqlalchemy.orm import Session, sessionmaker

from app.actions import exceptions as exceptions_action
from app.actions import lenses, redaction, system_trace
from app.actions import questions as questions_action
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import DESIGN_TOKENS_FILE, FONTS_DIR, AppConfig
from app.db import session_scope
from app.domain.enums import VerificationStatus, VersionState
from app.domain.exports import (
    ExportCapability,
    ExportCause,
    ExportGapReport,
    ExportInput,
    ExportKnowHow,
    ExportQuestion,
    ExportRealityGap,
    ExportStory,
    ExportTerm,
    SourceEntry,
)
from app.domain.graph import Graph
from app.domain.quality import QualityCard, QualityInput
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import causes as causes_repo
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import gap as gap_repo
from app.repositories import read_memo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import export_html, exports, quality, sensemaking, views

Sessions = sessionmaker[Session]

FORMATS = ("md", "json", "csv", "html")
# The reality-gap finding types of Analysis A (B.22, §3.12.7) shown in §7.3 section 3.
REALITY_GAPS = {"known_adaptation", "unknown_rule", "disclosure_gap", "control_gap",
                "constraint_mismatch"}  # fmt: skip


def _dominant(counts: dict[str, int]) -> str:
    """The ASHEN category with most items (the first in ASHEN order on a tie)."""
    best = max(sensemaking.ASHEN, key=lambda k: counts.get(k, 0))
    return best if counts.get(best, 0) else "none described"


def sensemaking_content(
    session: Session, version_id: str, engagement_id: str, graph: Graph, names: dict[str, str]
) -> tuple[list[ExportStory], list[ExportCapability], list[ExportTerm], list[ExportKnowHow]]:
    """Stories, strengths and weaknesses, the glossary and know-how per decision point, from the
    version's checked interview items (names hidden, no verbatim quotes; §7.3)."""
    lens = lenses.load(session, version_id, engagement_id)
    on_map = [e for e in graph.elements if e.review_status != "rejected"]
    labels = {e.stable_key: e.label for e in on_map}

    def steps_of(about: object) -> list[str]:
        return [labels[k] for k in about if k in labels] if isinstance(about, list) else []

    def where(source_id: str, segment_ids: list[str]) -> str:
        anchor = lens.anchors.get(segment_ids[0], "") if segment_ids else ""
        return " ".join(x for x in (names.get(source_id, "Interview"), anchor) if x)

    stories: list[ExportStory] = []
    capabilities: list[ExportCapability] = []
    glossary: list[ExportTerm] = []
    seen: set[str] = set()
    for r in lens.items:
        about = r.payload.get("about_steps")
        if r.claim_type == "story":
            stories.append(ExportStory(
                label=lens.hide(str(r.payload.get("text", ""))),
                fragment_type=str(r.payload.get("fragment_type", "other")),
                steps=steps_of(about), where=where(r.source_id, r.segment_ids),
            ))  # fmt: skip
        elif r.claim_type == "capability":
            capabilities.append(ExportCapability(
                kind=str(r.payload.get("kind", "")), dimension=str(r.payload.get("dimension", "")),
                text=lens.hide(str(r.payload.get("text", ""))), steps=steps_of(about),
            ))  # fmt: skip
        elif r.claim_type == "sme_term":
            term = str(r.payload.get("term", ""))
            if term.lower() not in seen:
                seen.add(term.lower())
                glossary.append(ExportTerm(
                    term=lens.hide(term),
                    plain_meaning=lens.hide(str(r.payload.get("plain_meaning", ""))),
                    steps=steps_of(about),
                ))  # fmt: skip
    know_how: list[ExportKnowHow] = []
    for e in on_map:
        kh = lenses.know_how(lens, e.stable_key, e.kind, e.work_type)
        if kh is not None:
            counts = {k: len(v) for k, v in kh.ashen.items()}
            know_how.append(ExportKnowHow(
                element_id=e.id, knowledge_risk=kh.knowledge_risk, dominant=_dominant(counts),
            ))  # fmt: skip
    return stories, capabilities, glossary, know_how


@cache
def html_assets() -> tuple[dict[str, object], dict[str, bytes]]:
    """The shared design tokens and the self-hosted font files, read once."""
    tokens = json.loads(DESIGN_TOKENS_FILE.read_text(encoding="utf-8"))
    fonts = {path.name: path.read_bytes() for path in sorted(FONTS_DIR.glob("*.woff2"))}
    return tokens, fonts


def export_input(
    config: AppConfig,
    session: Session,
    version_id: str,
    graph: Graph,
    every: Graph | None = None,
) -> ExportInput | None:
    """`graph` is the map as one; `every` the graph with every line (built here when not given;
    the quality card passes the one it already built)."""
    version = versions_repo.get(session, version_id)
    if version is None:
        return None
    terms = redaction.name_replacements(session, version.engagement_id)
    sources = sources_repo.get_many(session, map_repo.version_source_ids(session, version_id))
    published_at, published_by = versions_repo.publication(session, version_id)
    open_questions = [
        ExportQuestion(
            question=q.question,
            phase_name=q.phase_name,
            element_label=q.element_label,
            reason=q.reason,
        )
        for q in questions_action.question_views(session, version_id, version.engagement_id)
        if q.status == "open"
    ]
    # Pending cause-library entries on this map's steps, and its finalised gap reports (P10).
    labels = {e.stable_key: e.label for e in graph.elements if e.review_status != "rejected"}
    causes = [
        ExportCause(
            element_label=labels[c.element_stable_key],
            divergence_type=c.divergence_type,
            pattern=redaction.hide(c.pattern, terms),
            inferred_cause=redaction.hide(c.inferred_cause, terms),
        )
        for c in causes_repo.for_engagement(session, version.engagement_id)
        if c.validation_result == "pending" and c.element_stable_key in labels
    ]
    accepted = {"added_question", "added_cause", "added_step"}
    gap_reports = [
        ExportGapReport(
            mode=a.mode,
            finalised_at=a.finalised_at or "",
            accepted=[
                redaction.hide(f.title, terms)
                for f in gap_repo.findings(session, a.id)
                if f.disposition in accepted
            ],
        )
        for a in reversed(gap_repo.for_version(session, version_id))
        if a.status == "finalised"
    ]
    names = {s.id: redaction.hide(s.filename, terms) for s in sources}
    every = every or versions_action.build_graph(session, version_id, every_line=True)
    view_graphs: dict[str, Graph] = (
        {str(v): views.view_graph(every, v) for v in views.VIEWS}
        if every is not None and any(e.view_membership for e in every.elements)
        else {}
    )
    reality_gaps = [
        ExportRealityGap(
            gap_class=f.gap_class or "unexplained",
            title=redaction.hide(f.title, terms),
            stated_reason=redaction.hide(f.stated_reason, terms),
        )
        for a in reversed(gap_repo.for_version(session, version_id))
        if a.status == "finalised" and a.mode == "internal"
        for f in gap_repo.findings(session, a.id)
        if f.finding_type in REALITY_GAPS
        and f.verification_status == "verified"
        and f.disposition != "dismissed"
    ]
    stories, capabilities, glossary, know_how = sensemaking_content(
        session, version_id, version.engagement_id, graph, names
    )
    exceptions = (
        exceptions_action.report_for(session, version_id, "done", every) if view_graphs else None
    )
    return ExportInput(
        exceptions=exceptions,
        stories=stories,
        capabilities=capabilities,
        glossary=glossary,
        know_how=know_how,
        view_graphs=view_graphs,
        reality_gaps=reality_gaps,
        graph=graph,
        sources=[
            SourceEntry(
                id=s.id,
                name=redaction.hide(s.filename, terms),
                kind=s.kind,
                version_date=s.version_date,
                owner=redaction.hide(s.owner, terms),
                controlled_copy=s.controlled_copy,
            )
            for s in sources
        ],
        published_at=published_at,
        validated_by=published_by or actor_name(config),
        open_questions=open_questions,
        causes=causes,
        gap_reports=gap_reports,
        outside_flow_claims=claims_repo.counts(session, version_id).get("outside_flow", 0),
        outside_flow_questions=claims_repo.unknown_count(session, version_id, outside_flow=True),
    )


def render_exports(data: ExportInput) -> dict[str, str]:
    tokens, fonts = html_assets()
    return {
        "md": exports.render_master_map_md(data),
        "json": exports.render_graph_json(data),
        "csv": exports.render_raci_csv(data),
        "html": export_html.render_map_html(data, tokens, fonts),
    }


def card_for(config: AppConfig, session: Session, version_id: str) -> QualityCard | None:
    """Work out the quality card of a version as it is now (not stored). Read-only: the rows it
    reads several times are read once (DECISIONS 91)."""
    versions_action.give_step_codes(session, version_id)  # a read-only request gives none
    with read_memo.read_only(session):
        return _card_for(config, session, version_id)


def _card_for(config: AppConfig, session: Session, version_id: str) -> QualityCard | None:
    every = versions_action.build_graph(session, version_id, every_line=True)
    if every is None:
        return None
    graph = views.combined(every)  # the map as one, built once
    data = export_input(config, session, version_id, graph, every)
    if data is None:
        return None
    version = versions_repo.get(session, version_id)
    assert version is not None
    on_map = {e.id for e in exports.on_the_map(graph).elements}
    claim_ids = [
        cid
        for element_id, ids in map_repo.element_claims(session, version_id).items()
        if element_id in on_map
        for cid in ids
    ]
    unverified = sum(
        1
        for c in claims_repo.claims_by_id(session, claim_ids).values()
        if c.verification_status != VerificationStatus.VERIFIED.value
    )
    pending = sum(
        1 for p in map_repo.merge_proposals(session, version_id) if p.decision == "pending"
    )
    traced = system_trace.traced_steps(session, version_id)
    chosen = {r.id: r.disposition for r in map_repo.elements(session, version_id) if r.disposition}
    return quality.build_quality_card(
        QualityInput(
            graph=graph,
            lint=versions_action.lint_graph(
                every, versions_action.story_types(session, version_id), traced, chosen
            ),
            traced=sorted(traced),
            pending_merges=pending,
            open_image_suggestions=map_repo.suggested_image_count(session, version_id),
            unverified_claims=unverified,
            exports=render_exports(data),
            hidden_terms=[
                t.term for t in redaction.name_replacements(session, version.engagement_id)
            ],
            source_kinds=[s.kind for s in data.sources],
        )
    )


def get_quality_card(config: AppConfig, sessions: Sessions, version_id: str) -> Result[QualityCard]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        stored = versions_repo.quality_card(session, version_id)
        if version.state != VersionState.DRAFT.value and stored is not None:
            return Ok(QualityCard.model_validate(stored))
        card = card_for(config, session, version_id)
        if card is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        if version.state == VersionState.DRAFT.value:
            versions_repo.set_quality_card(session, version_id, card.model_dump(mode="json"))
        return Ok(card)


def draft_card(config: AppConfig, session: Session, engagement_id: str) -> QualityCard | None:
    """The quality card of the engagement's current draft, worked out now (None without one)."""
    draft = versions_repo.current_draft(session, engagement_id)
    return card_for(config, session, draft.id) if draft else None
