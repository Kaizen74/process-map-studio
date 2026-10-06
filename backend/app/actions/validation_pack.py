"""The validation session pack (API_CONTRACT.md → GET /versions/{vid}/validation-pack; PRD
Appendix F.7, criterion 75; C6): gathered from the version's As done view, its combined map, its
capability notes and its open questions, names hidden; rendered by `services.validation_pack`.
Deterministic; nothing is sent to Claude."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, questions, redaction, versions
from app.db import session_scope
from app.domain.models import ExportFile
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import PackStep, ValidationPackInput
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo
from app.services import validation_pack as pack

Sessions = sessionmaker[Session]

MEDIA = "text/markdown; charset=utf-8"


def validation_pack(sessions: Sessions, version_id: str) -> Result[ExportFile]:
    notes = lenses.get_capability_notes(sessions, version_id)
    if isinstance(notes, Err):
        return notes
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
        engagement = engagements_repo.get(session, version.engagement_id)
        done = versions.build_graph(session, version_id, every_line=True, view="done")
        combined = versions.build_graph(session, version_id)
        if engagement is None or done is None or combined is None:
            return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
        terms = redaction.name_replacements(session, engagement.id)
        open_questions = [
            (q.element_label, q.question)
            for q in questions.question_views(session, version_id, engagement.id)
            if q.status == "open"
        ]
    roles = {r.id: r.name for r in done.roles}
    labels = {e.id: e.label for e in done.elements}
    steps = [
        PackStep(label=e.label, role=roles.get(e.lane_role_id or "", ""))
        for e in done.elements
        if e.kind in pack.STEP_KINDS and e.review_status != "rejected"
    ]
    gaps = [
        (labels[x.from_], labels[x.to])
        for x in done.edges
        if x.kind == "gap" and x.from_ in labels and x.to in labels
    ]
    process = redaction.hide(engagement.process_name or engagement.name, terms)
    data = ValidationPackInput(
        process=process,
        version_label=version.label,
        steps=steps,
        gaps=gaps,
        contrasts=pack.contrasts(combined),
        strengths=[n.text for n in notes.value if n.kind == "strength"],
        weaknesses=[n.text for n in notes.value if n.kind == "weakness"],
        questions=open_questions,
        stamp=f"Process Map Studio · {process} {version.label} · enter the outcomes as edits on "
        "the Review screen",
    )
    return Ok(
        ExportFile(
            filename=f"validation-pack-{version.label}.md",
            media_type=MEDIA,
            content=pack.render_validation_pack(data),
        )
    )
