"""The Reality pack export (PRD §3.18.6, §7.4; API_CONTRACT.md → Reality snapshot → export;
P13d): the published version's frozen snapshot drawn as one offline HTML file for A3 or 16:9
pages. The same rule as every export: a published version with a green quality card."""

from __future__ import annotations

from functools import cache

from sqlalchemy.orm import Session, sessionmaker

from app.actions import publish, reality
from app.actions import quality as quality_action
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import REALITY_CSS_FILE, AppConfig
from app.db import session_scope
from app.domain.enums import VersionState
from app.domain.models import ExportFile
from app.domain.quality import QualityCard
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import versions as versions_repo
from app.services import export_reality

Sessions = sessionmaker[Session]

BAD_LAYOUT = "Choose the A3 or the 16:9 layout."
MEDIA = "text/html; charset=utf-8"


@cache
def _reality_css() -> str:
    return REALITY_CSS_FILE.read_text(encoding="utf-8")


def export_pack(config: AppConfig, sessions: Sessions, version_id: str,
                layout: str) -> Result[ExportFile]:  # fmt: skip
    if layout not in export_reality.LAYOUTS:
        return Err(ErrorKind.VALIDATION, BAD_LAYOUT, {"field": "layout"})
    actor = actor_name(config)
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        stored = versions_repo.quality_card(session, version_id)
        published = version.state in (VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value)
        card = QualityCard.model_validate(stored) if stored else None
        if not published or card is None or not card.all_green:
            return Err(ErrorKind.CONFLICT, publish.NOT_EXPORTABLE)
        snapshot = reality.snapshot_of(session, version)  # frozen for a published version
        strength = publish.version_signal(session, version_id)
        tokens, fonts = quality_action.html_assets()
        content = export_reality.render_pack(
            snapshot, layout,
            signal=strength.label if strength else "", tokens=tokens, fonts=fonts,
            reality_css=_reality_css(),
        )  # fmt: skip
        audit.record(
            session, actor=actor, action="Exported Reality pack", target_type="version",
            target_id=version_id, engagement_id=version.engagement_id, version_id=version_id,
            after={"layout": layout},
        )  # fmt: skip
        name = (f"{publish.slug(snapshot.process_name)}-{publish.slug(version.label)}-"
                f"reality-pack-{layout}.html")  # fmt: skip
    return Ok(ExportFile(filename=name, media_type=MEDIA, content=content))
