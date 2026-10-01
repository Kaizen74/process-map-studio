"""The coverage report (PRD §3.12.8, criterion 50, A.8; C4): what the interviews covered and what
still needs asking, worked out on request from the version's checked interview claims and items
and its As done view. Deterministic; nothing is sent to Claude.

Step labels come from the graph, names already hidden; roles, never people.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import versions
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import CoverageReport
from app.repositories import claims as claims_repo
from app.services import interview_templates, sensemaking

Sessions = sessionmaker[Session]


def get_coverage(sessions: Sessions, version_id: str) -> Result[CoverageReport]:
    bank = interview_templates.load_bank()
    if isinstance(bank, Err):
        return bank
    with session_scope(sessions) as session:
        done = versions.build_graph(session, version_id, every_line=True, view="done")
        if done is None:
            return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
        claims = claims_repo.verified_with_steps(session, version_id)
    dims, about = sensemaking.coverage_dimensions(claims, done)
    wording = {q.id: q.wording for q in bank.value.questions}
    return Ok(
        CoverageReport(
            version_id=version_id,
            dimensions=dims,
            follow_up_questions=sensemaking.follow_up_questions(dims, about, wording),
        )
    )
