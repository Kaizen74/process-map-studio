"""Reality snapshots (PRD §3.5 `reality_snapshots`, §3.18.1; P13b): the only database access.
One row per version (the As done view); a frozen row is never written again."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.tables import RealitySnapshot

DONE = "done"


@dataclass(frozen=True, slots=True)
class Stored:
    payload: dict[str, Any]
    inputs_hash: str
    rules_version: str
    app_version: str
    frozen: bool


def _row(session: Session, version_id: str) -> RealitySnapshot | None:
    return session.scalars(
        select(RealitySnapshot)
        .where(RealitySnapshot.version_id == version_id, RealitySnapshot.view == DONE)
        .order_by(RealitySnapshot.id)
    ).first()


def get(session: Session, version_id: str) -> Stored | None:
    row = _row(session, version_id)
    if row is None:
        return None
    return Stored(dict(row.payload), row.inputs_hash, row.rules_version, row.app_version,
                  bool(row.frozen))  # fmt: skip


def save(session: Session, version_id: str, stored: Stored) -> None:
    """Keep the version's snapshot (never over a frozen one)."""
    row = _row(session, version_id)
    if row is not None and row.frozen:
        return
    if row is None:
        row = RealitySnapshot(version_id=version_id, view=DONE)
        session.add(row)
    row.payload = stored.payload
    row.inputs_hash = stored.inputs_hash
    row.rules_version = stored.rules_version
    row.app_version = stored.app_version
    row.frozen = stored.frozen
    session.flush()
