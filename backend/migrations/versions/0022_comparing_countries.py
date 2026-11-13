"""Comparing countries (2026-11-13, Eric; DECISIONS 98, PRD §3.19).

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-13

Additive only (PRD constraint 16): upgrade() adds two columns and three tables; downgrade()
removes only them.
- engagements.country: the country the engagement covers ("" when not known).
- engagements.reference_engagement_id: the other country's engagement it started from.
- country_comparisons, country_pairs, country_differences: two published maps compared, Eric's
  step pairs by stable key, and his decisions on each difference.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def _row(name: str, *columns: sa.Column, keys: list[tuple[str, str]]) -> None:  # type: ignore[type-arg]
    op.create_table(
        name,
        *columns,
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        *[sa.ForeignKeyConstraint([c], [t], ondelete="CASCADE") for c, t in keys],
        sa.PrimaryKeyConstraint("id"),
    )
    for column, _ in keys:
        op.create_index(op.f(f"ix_{name}_{column}"), name, [column], unique=False)


def upgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.add_column(sa.Column("country", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("reference_engagement_id", ID, nullable=True))
        batch.create_index("ix_engagements_reference_engagement_id", ["reference_engagement_id"])
        batch.create_foreign_key(
            "fk_engagements_reference_engagement_id",
            "engagements",
            ["reference_engagement_id"],
            ["id"],
            ondelete="SET NULL",
        )
    _row(
        "country_comparisons",
        sa.Column("reference_engagement_id", ID, nullable=False),
        sa.Column("other_engagement_id", ID, nullable=False),
        sa.Column("reference_version_id", ID, nullable=False),
        sa.Column("other_version_id", ID, nullable=False),
        sa.Column("suggest_job_id", ID, nullable=True),
        keys=[
            ("reference_engagement_id", "engagements.id"),
            ("other_engagement_id", "engagements.id"),
            ("reference_version_id", "map_versions.id"),
            ("other_version_id", "map_versions.id"),
        ],
    )
    _row(
        "country_pairs",
        sa.Column("comparison_id", ID, nullable=False),
        sa.Column("reference_key", sa.Text(), nullable=True),
        sa.Column("other_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        keys=[("comparison_id", "country_comparisons.id")],
    )
    _row(
        "country_differences",
        sa.Column("comparison_id", ID, nullable=False),
        sa.Column("diff_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_class", sa.String(length=16), nullable=True),
        sa.Column("reason_note", sa.Text(), nullable=False),
        sa.Column("grade", sa.String(length=12), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        keys=[("comparison_id", "country_comparisons.id")],
    )


def downgrade() -> None:
    for name in ("country_differences", "country_pairs", "country_comparisons"):
        op.drop_table(name)
    with op.batch_alter_table("engagements") as batch:
        batch.drop_constraint("fk_engagements_reference_engagement_id", type_="foreignkey")
        batch.drop_index("ix_engagements_reference_engagement_id")
        batch.drop_column("reference_engagement_id")
        batch.drop_column("country")
