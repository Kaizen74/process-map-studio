"""Role costs and value assumptions (PRD §3.5 `role_costs`, `value_assumptions`; §3.14; R9b): the
only database access. Costs are per role, never per person."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.repositories.tables import RoleCost, ValueAssumption


def role_costs(session: Session, engagement_id: str) -> dict[str, tuple[float, str]]:
    """Role ID → (hourly cost, note)."""
    rows = session.scalars(select(RoleCost).where(RoleCost.engagement_id == engagement_id))
    return {r.role_id: (r.hourly_cost, r.note) for r in rows}


def set_role_cost(session: Session, engagement_id: str, role_id: str, cost: float | None,
                  currency: str, note: str) -> None:  # fmt: skip
    session.execute(delete(RoleCost).where(RoleCost.engagement_id == engagement_id,
                                           RoleCost.role_id == role_id))  # fmt: skip
    if cost is not None:
        session.add(RoleCost(engagement_id=engagement_id, role_id=role_id, hourly_cost=cost,
                             currency=currency, note=note))  # fmt: skip
    session.flush()


def assumptions(session: Session, engagement_id: str) -> dict[str, tuple[float, str]]:
    """Disposition → (reduction percent, note), for those Eric has set."""
    rows = session.scalars(
        select(ValueAssumption).where(ValueAssumption.engagement_id == engagement_id)
    )
    return {r.disposition: (r.reduction_pct, r.note) for r in rows}


def set_assumption(session: Session, engagement_id: str, disposition: str, pct: float,
                   note: str) -> None:  # fmt: skip
    session.execute(delete(ValueAssumption).where(
        ValueAssumption.engagement_id == engagement_id,
        ValueAssumption.disposition == disposition,
    ))  # fmt: skip
    session.add(ValueAssumption(engagement_id=engagement_id, disposition=disposition,
                                reduction_pct=pct, note=note))  # fmt: skip
    session.flush()
