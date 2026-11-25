"""The `compass-return` file from a published version (API_CONTRACT.md → Capability Compass
return file; DECISIONS 97). Gathers what the published map found, hides names, and refuses to
hand out a file that still holds a hidden name or anything shaped like a key."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import comparisons, redaction
from app.actions import leadership as leadership_action
from app.actions import reality as reality_action
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.compass import CompassLink
from app.domain.enums import SourceKind, VersionState
from app.domain.graph import Graph, GraphElement
from app.domain.models import ExportFile, VersionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import codes as codes_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import intent as intent_repo
from app.repositories import sources as sources_repo
from app.repositories import testing as testing_repo
from app.repositories import versions as versions_repo
from app.services import accountability, exports
from app.services import compass_return as rules
from app.services import grade as grade_rules
from app.services import sop_register as register_rules

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
# "<key>_compass_return.json" / ".md" (Eric's brief 2026-11-13, DECISIONS 98).
FILES = {"json": ("compass_return.json", "application/json"),
         "md": ("compass_return.md", "text/markdown; charset=utf-8")}  # fmt: skip
SECRET_MARKERS = rules.SECRET_MARKERS


def _counts(e: GraphElement) -> tuple[int, int]:
    """(documents, interviews) with a checked passage that speaks to the step."""
    speaking = {(ev.source_id, ev.source_kind) for ev in e.evidence
                if ev.verified and ev.stance != "silent"}  # fmt: skip
    interviews = sum(1 for _, kind in speaking if kind == SourceKind.INTERVIEW_TRANSCRIPT.value)
    return len(speaking) - interviews, interviews


def _rights(graph: Graph, hide: Callable[[str], str]) -> dict[str, accountability.Rights]:
    """§3.20: element ID → its three roles, names hidden, for every decision and approval."""
    roles = {r.id: hide(r.name) for r in graph.roles}
    return {e.id: r for e in graph.elements if (r := accountability.rights(e, roles)) is not None}


def _steps(graph: Graph, rights: dict[str, accountability.Rights]) -> list[rules.Step]:
    roles = {r.id: r.name for r in graph.roles}
    out = []
    for e in exports.steps(exports.on_the_map(graph)):
        documents, interviews = _counts(e)
        out.append(rules.Step(
            code=e.code or "", label=e.label, kind=e.kind, lane=roles.get(e.lane_role_id or "", ""),
            work_type=e.work_type, mechanism=e.decision.mechanism, provenance=e.provenance,
            documents=documents, interviews=interviews, knowledge_risk=e.k_risk,
            rights=rights.get(e.id),
        ))  # fmt: skip
    return [s for s in out if s.code]


def _at_decisions(graph: Graph, rights: dict[str, accountability.Rights],
                  d: rules.Discrepancy, element_ids: list[str]) -> rules.Discrepancy:  # fmt: skip
    """A Different role discrepancy's three roles: the first decision or approval step it is at;
    the other such steps with other values are named in its detail."""
    if d.topic != rules.DECISION_RIGHT:
        return d
    codes = {e.id: e.code or "" for e in graph.elements}
    at = [i for i in element_ids if i in rights]
    if not at:
        return d
    first = rights[at[0]]
    also = [codes[i] for i in at[1:] if rights[i] != first and codes.get(i)]
    return replace(d, rights=first, also_at=also)


def _reality(session: Session, version: VersionView, hide: object
             ) -> tuple[list[rules.Discrepancy], list[list[str]], list[rules.Intent]]:  # fmt: skip
    """The published version's frozen snapshot: its X codes and its confirmed intent."""
    assert callable(hide)
    snapshot = reality_action.snapshot_of(session, version)
    kinds = {e.id: e.kind for e in map_repo.elements(session, version.id)}
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
            topic=rules.discrepancy_topic([kinds.get(i, "") for i in c.element_ids], list(c.types)),
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
    return discrepancies, [list(c.element_ids) for c in snapshot.codes], intents


def _sops(session: Session, engagement_id: str, graph: Graph, hide: Callable[[str], str],
          departing_at: set[str] | None) -> list[rules.Sop]:  # fmt: skip
    """§3.20: one finding per SOP or manual (the newest when the same one is there twice), with
    the published map's steps citing it in a checked passage and, of those, the ones done
    differently: with a Reality discrepancy when the views are on (`departing_at`), otherwise
    where the step's sources disagree."""
    roles = {r.id: r.name for r in engagements_repo.list_roles(session, engagement_id)}
    found = register_rules.entries(sources_repo.list_for_engagement(session, engagement_id),
                                   roles, date.today().isoformat())  # fmt: skip
    current = [e for e in found if not e.older]
    codes = codes_repo.ensure(session, engagement_id, codes_repo.SOP,
                              [e.source_id for e in current])  # fmt: skip
    steps = exports.steps(exports.on_the_map(graph))
    out = []
    for e in current:
        if e.source_id not in codes:
            continue  # a read-only request gives no new code
        cited = [s for s in steps
                 if any(ev.source_id == e.source_id and ev.verified and ev.stance != "silent"
                        for ev in s.evidence)]  # fmt: skip
        departing = [s for s in cited
                     if (s.id in departing_at if departing_at is not None
                         else bool(s.divergence_types))]  # fmt: skip
        out.append(rules.Sop(
            code=codes[e.source_id], title=hide(e.title), owner_role=hide(e.owner)[:80],
            updated_by=hide(e.updated_by)[:80], version_date=e.version_date,
            last_reviewed=e.last_reviewed, review_due=e.review_due, controlled=e.controlled,
            governed=len(cited), departing=len(departing),
            by_discrepancies=departing_at is not None,
            older_also=any(o.older and o.title.casefold() == e.title.casefold() for o in found),
        ))  # fmt: skip
    return sorted(out, key=lambda x: int(x.code.split("-")[1]))


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
        if link is None or engagement is None:
            return Err(ErrorKind.CONFLICT, NO_HANDOFF)
        chosen = list(dict.fromkeys(c.strip() for c in cells if c.strip()))
        if any(c not in link.cell_refs for c in chosen):  # never an ID this app made up
            return Err(ErrorKind.VALIDATION, UNKNOWN_CELL, {"field": "cells"})
        graph = versions_action.build_graph(session, version_id)
        assert graph is not None
        terms = redaction.name_replacements(session, version.engagement_id)

        def hide(text: str) -> str:
            return redaction.hide(text, terms)

        discrepancies, at_steps, intents = (
            _reality(session, version, hide) if reality_action.enabled(config) else ([], [], [])
        )
        tested = [rules.Tested(ref=t.ref, text=hide(t.text), verdict=t.verdict,
                               evidence_refs=list(t.evidence_refs), note=hide(t.note))
                  for t in testing_repo.list_for(session, version.engagement_id)]  # fmt: skip
        variations, other_hidden = comparisons.variations_for(config, session, engagement.id,
                                                              version_id)  # fmt: skip
        rights = _rights(graph, hide)
        by_code = {e.code: e.id for e in graph.elements if e.code}
        variations = [
            replace(v, rights=rights.get(by_code.get(v.step_code, "")))
            if v.topic == rules.DECISION_RIGHT
            else v
            for v in variations
        ]
        discrepancies = [_at_decisions(graph, rights, d, ids)
                         for d, ids in zip(discrepancies, at_steps, strict=True)]  # fmt: skip
        sops = _sops(session, engagement.id, graph, hide,
                     {i for ids in at_steps for i in ids}
                     if reality_action.enabled(config) else None)  # fmt: skip
        process_cell = f"{link.cluster_ref}.Process"
        data = rules.Inputs(
            engagement_key=link.key, pilot_ref=link.pilot_ref, cluster_ref=link.cluster_ref,
            cells=chosen, generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            process_name=graph.process.name, version_label=version.label,
            steps=_steps(graph, rights),
            discrepancies=discrepancies, intents=intents, tested=tested,
            country=link.country or engagement.country, variations=variations, sops=sops,
            process_cell=process_cell if process_cell in link.cell_refs else "",
            summary=leadership_action.summary_of(config, session, version, graph),
        )  # fmt: skip
        content = rules.render_json(data) if fmt == "json" else rules.render_text(data)
        if rules.leaks(content, [t.term for t in terms] + other_hidden, SECRET_MARKERS):
            return Err(ErrorKind.CONFLICT, LEAK)
        name, media = FILES[fmt]
        audit.record(session, actor=actor_name(config), action="Exported compass-return",
                     target_type="version", target_id=version_id,
                     engagement_id=version.engagement_id,
                     after={"format": fmt, "findings": len(rules.findings(data)),
                            "relates_to": [link.pilot_ref, link.cluster_ref, *chosen]})  # fmt: skip
        filename = f"{re.sub(r'[^A-Za-z0-9-]+', '-', link.key).strip('-') or 'engagement'}_{name}"
        return Ok(ExportFile(filename=filename, media_type=media, content=content))
