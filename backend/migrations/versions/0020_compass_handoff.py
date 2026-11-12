"""Capability Compass hand-off and What we are testing (2026-11-12, Eric; DECISIONS 95).

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-12

Additive only (PRD constraint 16): upgrade() adds one column and one table; downgrade() removes
only them.
- engagements.compass: what the engagement keeps of the hand-off it started from (key, pilot
  ref, cluster ref and name, cell IDs, suggested probes, readiness), exactly as received; null
  for an engagement made without one.
- testing_items: the design principles from the hand-off and the hypotheses Eric adds by hand,
  each with his verdict and the step or discrepancy codes behind it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def upgrade() -> None:
    op.add_column("engagements", sa.Column("compass", sa.JSON(), nullable=True))
    op.create_table(
        "testing_items",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("ref", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("refuted_by", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_testing_items_engagement_id"), "testing_items", ["engagement_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_testing_items_engagement_id"), table_name="testing_items")
    op.drop_table("testing_items")
    with op.batch_alter_table("engagements") as batch:
        batch.drop_column("compass")
