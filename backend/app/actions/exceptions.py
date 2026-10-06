"""Exceptions, rework and workarounds (API_CONTRACT.md → GET /versions/{vid}/exceptions; X2,
2026-10-06): one view of the map with, for each step, the SME's own words from its verified
claims (variation condition, stated reason, how often; names hidden) and whether a workaround
story is told about it, handed to `services.exceptions`. Deterministic; never changes the map."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, redaction, versions
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import ExceptionEdgeInput, ExceptionReport, ExceptionStepInput, View
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import versions as versions_repo
from app.services import exceptions
from app.services import interview_templates as templates

Sessions = sessionmaker[Session]
# Used only if the question bank can't be read; the bank's own wording of M5.s2.
ASK_FALLBACK = "How often does something like that happen?"


def frequency_question() -> str:
    bank = templates.load_bank()
    if isinstance(bank, Err) or not any(q.id == exceptions.FREQUENCY_QUESTION
                                        for q in bank.value.questions):  # fmt: skip
        return ASK_FALLBACK
    return bank.value.question(exceptions.FREQUENCY_QUESTION).wording


def report_for(session: Session, version_id: str, view: View) -> ExceptionReport | None:
    version = versions_repo.get(session, version_id)
    graph = versions.build_graph(session, version_id, every_line=True, view=view)
    if version is None or graph is None:
        return None
    terms = redaction.name_replacements(session, version.engagement_id)

    def hide(text: object) -> str:
        return redaction.hide(str(text or ""), terms).strip()

    lanes = {r.id: r.name for r in graph.roles}
    claims_of = map_repo.element_claims(session, version_id)
    records = claims_repo.by_ids(session, [c for ids in claims_of.values() for c in ids])
    told = lenses.load(session, version_id, version.engagement_id)
    steps = []
    for e in graph.elements:
        if e.review_status == "rejected":
            continue
        answers = [records[c] for c in claims_of.get(e.id, [])
                   if c in records and records[c].verification_status == "verified"
                   and records[c].account_type is not None]  # fmt: skip
        lived = [a for a in answers if a.account_type == "lived"]
        stories = [r for r in told.items if r.claim_type == "story"
                   and lenses.is_about(r, e.stable_key)]  # fmt: skip
        workaround = [r for r in stories if r.payload.get("fragment_type") == "workaround"]
        frequencies = [a.payload.get("frequency") for a in answers]
        frequencies += [r.payload.get("frequency") for r in workaround]
        steps.append(ExceptionStepInput(
            element_id=e.id, label=e.label, kind=e.kind,
            lane=lanes.get(e.lane_role_id or "", ""),
            condition=next((hide(a.payload.get("variation_condition")) for a in lived
                            if hide(a.payload.get("variation_condition"))), ""),
            stated_reason=next((hide(a.payload.get("stated_reason")) for a in lived
                                if hide(a.payload.get("stated_reason"))), ""),
            frequency=next((hide(f) for f in frequencies if hide(f)), ""),
            practiced_only=e.source_state == "practiced_only",
            workaround_story=bool(workaround),
        ))  # fmt: skip
    edges = [ExceptionEdgeInput(from_id=x.from_, to_id=x.to, kind=x.kind, label=hide(x.label))
             for x in graph.edges]  # fmt: skip
    return exceptions.analyse(steps, edges, view, frequency_question())


def get_exceptions(
    sessions: Sessions, version_id: str, view: View | None = None
) -> Result[ExceptionReport]:
    """The report for a view (As done unless As documented is asked for)."""
    with session_scope(sessions) as session:
        found = report_for(session, version_id, view or "done")
    if found is None:
        return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
    return Ok(found)
