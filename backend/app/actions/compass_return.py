"""The `compass-return` file from a published version (API_CONTRACT.md → Capability Compass
return file; DECISIONS 97). Gathers what the published map found, hides names, and refuses to
hand out a file that still holds a hidden name or anything shaped like a key."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import reality as reality_action
from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.publish import slug
from app.config import AppConfig
from app.db import session_scope
from app.domain.compass import CompassLink
from app.domain.enums import SourceKind, VersionState
from app.domain.graph import Graph, GraphElement
from app.domain.models import ExportFile, VersionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import codes as codes_repo
from app.repositories import engagements as engagements_repo
from app.repositories import intent as intent_repo
from app.repositories import testing as testing_repo
from app.repositories import versions as versions_repo
from app.services import compass_return as rules
from app.services import exports
from app.services import grade as grade_rules

Sessions = sessionmaker[Session]

NOT_PUBLISHED = "Publish a version first: the return file is made from a published map."
NO_HANDOFF = (
    "This engagement didn't start from a Capability Compass hand-off, so there is no "
    "engagement key to return findings under."
)
UNKNOWN_CELL = "Choose cells from this engagement's hand-off."
UNKNOWN_FORMAT = "Choose JSON or readable text."
LEAK = (
    "The return file would have held a name on the list of names to hide, so nothing was "
    "downloaded. Check the list of names to hide and the wording of the map, then try again."
)
FILES = {"json": ("compass-return.json", "application/json"),
         "md": ("compass-return.md", "text/markdown; charset=utf-8")}  # fmt: skip
SECRET_MARKERS = ("sk-" + "ant-", "api_key", "x-api-key")


def _counts(e: GraphElement) -> tuple[int, int]:
    """(documents, interviews) with a checked passage that speaks to the step."""
    speaking = {(ev.source_id, ev.source_kind) for ev in e.evidence
                if ev.verified and ev.stance != "silent"}  # fmt: skip
    interviews = sum(1 for _, kind in speaking if kind == SourceKind.INTERVIEW_TRANSCRIPT.value)
    return len(speaking) - interviews, interviews


def _steps(graph: Graph) -> list[rules.Step]:
    roles = {r.id: r.name for r in graph.roles}
    out = []
    for e in exports.steps(exports.on_the_map(graph)):
        documents, interviews = _counts(e)
        out.append(rules.Step(
            code=e.code or "", label=e.label, kind=e.kind, lane=roles.get(e.lane_role_id or "", ""),
            work_type=e.work_type, mechanism=e.decision.mechanism, provenance=e.provenance,
            documents=documents, interviews=interviews, knowledge_risk=e.k_risk,
        ))  # fmt: skip
    return [s for s in out if s.code]


def _reality(session: Session, version: VersionView,
             hide: object) -> tuple[list[rules.Discrepancy], list[rules.Intent]]:  # fmt: skip
    """The published version's frozen snapshot: its X codes and its confirmed intent."""
    assert callable(hide)
    snapshot = reality_action.snapshot_of(session, version)
    discrepancies = []
    for c in snapshot.codes:
        suggested = grade_rules.for_discrepancy(
            documents=c.evidence.documents, interviews=c.evidence.interviews,
            system_cases=c.evidence.system_cases)  # fmt: skip
        discrepancies.append(rules.Discrepancy(
            code=c.code, title=hide(c.title), types=list(c.types), figure=c.delta.text,
            figure_label=c.delta.label, grade=c.grade.grade if c.grade else suggested,
            grade_by_owner=bool(c.grade and c.grade.chosen_by_owner), impact=c.impact_word,
            verdict=c.verdict.shown if c.verdict else None, documents=c.evidence.documents,
            interviews=c.evidence.interviews, system_cases=c.evidence.system_cases,
        ))  # fmt: skip
    codes = codes_repo.ensure(session, version.engagement_id, codes_repo.INTENT,
                              [i.id for i in snapshot.intents])  # fmt: skip
    intents = []
    for i in snapshot.intents:
        stored = intent_repo.get(session, i.id)
        if i.id in codes:
            intents.append(rules.Intent(
                code=codes[i.id], text=hide(i.text), kind=i.kind, result=i.result,
                target=hide(i.target), quoted=bool(stored and stored.origin == "document"),
            ))  # fmt: skip
    return discrepancies, intents


def export(config: AppConfig, sessions: Sessions, version_id: str, fmt: str,
           cells: list[str]) -> Result[ExportFile]:  # fmt: skip
    if fmt not in FILES:
        return Err(ErrorKind.VALIDATION, UNKNOWN_FORMAT, {"field": "fmt"})
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        if version.state not in (VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value):
            return Err(ErrorKind.CONFLICT, NOT_PUBLISHED)
        engagement = engagements_repo.get(session, version.engagement_id)
        link: CompassLink | None = engagement.compass if engagement else None
        if link is None:
            return Err(ErrorKind.CONFLICT, NO_HANDOFF)
        chosen = list(dict.fromkeys(c.strip() for c in cells if c.strip()))
        if any(c not in link.cell_refs for c in chosen):  # never an ID this app made up
            return Err(ErrorKind.VALIDATION, UNKNOWN_CELL, {"field": "cells"})
        graph = versions_action.build_graph(session, version_id)
        assert graph is not None
        terms = redaction.name_replacements(session, version.engagement_id)

        def hide(text: str) -> str:
            return redaction.hide(text, terms)

        discrepancies, intents = (
            _reality(session, version, hide) if reality_action.enabled(config) else ([], [])
        )
        tested = [rules.Tested(ref=t.ref, text=hide(t.text), verdict=t.verdict,
                               evidence_refs=list(t.evidence_refs), note=hide(t.note))
                  for t in testing_repo.list_for(session, version.engagement_id)]  # fmt: skip
        data = rules.Inputs(
            engagement_key=link.key, pilot_ref=link.pilot_ref, cluster_ref=link.cluster_ref,
            cells=chosen, generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            process_name=graph.process.name, version_label=version.label, steps=_steps(graph),
            discrepancies=discrepancies, intents=intents, tested=tested,
        )  # fmt: skip
        content = rules.render_json(data) if fmt == "json" else rules.render_text(data)
        if rules.leaks(content, [t.term for t in terms], SECRET_MARKERS):
            return Err(ErrorKind.CONFLICT, LEAK)
        name, media = FILES[fmt]
        audit.record(session, actor=actor_name(config), action="Exported compass-return",
                     target_type="version", target_id=version_id,
                     engagement_id=version.engagement_id,
                     after={"format": fmt, "findings": len(rules.findings(data)),
                            "relates_to": [link.pilot_ref, link.cluster_ref, *chosen]})  # fmt: skip
        filename = f"{slug(graph.process.name)}-{slug(version.label)}-{name}"
        return Ok(ExportFile(filename=filename, media_type=media, content=content))
