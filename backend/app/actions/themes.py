"""Emerging themes (API_CONTRACT.md → Emerging themes; Appendix E tier 3, criterion 58; C7b):
listed with the story fragments behind them, names hidden; accepted, renamed, dismissed or put
back by Eric, every change audited. Themes never change the map."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, redaction
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import ThemeFragment, ThemePatch, ThemeRecord, ThemeView
from app.repositories import audit
from app.repositories import claims as claims_repo
from app.repositories import engagements as engagements_repo
from app.repositories import themes as repo
from app.repositories import versions as versions_repo
from app.services import sensemaking

Sessions = sessionmaker[Session]

ENGAGEMENT_MISSING = "That engagement doesn't exist."
THEME_MISSING = "That theme doesn't exist."
STATUSES = ("proposed", "accepted", "dismissed")
MAX_NOTE = 500
ACTIONS = {"accepted": "Accepted emerging theme", "dismissed": "Dismissed emerging theme",
           "proposed": "Reopened emerging theme"}  # fmt: skip


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _views(
    session: Session, rows: list[ThemeRecord], terms: list[NameReplacement]
) -> list[ThemeView]:
    claims = claims_repo.claims_by_id(session, [c for r in rows for c in r.fragment_ids])
    first = [c.segment_ids[0] for c in claims.values() if c.segment_ids]
    anchors, _ = lenses.places(session, first)

    def hide(text: str) -> str:
        return redaction.hide(text, terms)

    out = []
    for row in rows:
        fragments = []
        for cid in row.fragment_ids:
            c = claims.get(cid)
            if c is None:
                continue
            segment = c.segment_ids[0] if c.segment_ids else ""
            fragments.append(ThemeFragment(
                claim_id=cid, text=hide(str(c.payload.get("text", ""))), quote=hide(c.quote),
                fragment_type=str(c.payload.get("fragment_type", "")), source_id=c.source_id,
                anchor=anchors.get(segment, ""),
            ))  # fmt: skip
        out.append(ThemeView(id=row.id, version_id=row.version_id, theme=hide(row.theme),
                             basis=hide(row.basis), status=row.status, note=row.note,
                             fragments=fragments, created_at=row.created_at))  # fmt: skip
    return out


def list_themes(sessions: Sessions, engagement_id: str) -> Result[list[ThemeView]]:
    """The current map's proposed themes and every theme Eric has decided, oldest first."""
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        current = versions_repo.current_map_id(session, engagement_id)
        rows = [
            r for r in repo.for_engagement(session, engagement_id)
            if r.status != repo.PROPOSED or r.version_id == current
        ]  # fmt: skip
        terms = redaction.name_replacements(session, engagement_id)
        return Ok(_views(session, rows, terms))


def update_theme(
    config: AppConfig, sessions: Sessions, theme_id: str, patch: ThemePatch
) -> Result[ThemeView]:
    if patch.status not in STATUSES:
        return _invalid("status", "Choose accepted, dismissed or proposed.")
    note = (patch.note or "").strip() if patch.note is not None else None
    if note is not None and (len(note) > MAX_NOTE or "\n" in note):
        return _invalid("note", f"Keep the note to one line of up to {MAX_NOTE} characters.")
    with session_scope(sessions) as session:
        row = repo.get(session, theme_id)
        if row is None:
            return Err(ErrorKind.NOT_FOUND, THEME_MISSING)
        terms = redaction.name_replacements(session, row.engagement_id)
        fields: dict[str, str] = {"status": patch.status}
        if patch.theme is not None:
            name = " ".join(patch.theme.split())
            if problem := sensemaking.theme_problem(name, [t.term for t in terms]):
                return _invalid("theme", problem)
            fields["theme"] = name
        if note is not None:
            fields["note"] = note
        before = {k: getattr(row, k) for k in fields}
        changed = {k: v for k, v in fields.items() if before[k] != v}
        if changed:
            action = (
                ACTIONS[patch.status]
                if "status" in changed
                else ("Renamed emerging theme" if "theme" in changed else "Edited emerging theme")
            )
            row = repo.update(session, theme_id, changed)
            audit.record(session, actor=actor_name(config), action=action,
                         target_type="theme", target_id=theme_id,
                         engagement_id=row.engagement_id,
                         before={k: before[k] for k in changed}, after=changed)  # fmt: skip
        return Ok(_views(session, [row], terms)[0])
