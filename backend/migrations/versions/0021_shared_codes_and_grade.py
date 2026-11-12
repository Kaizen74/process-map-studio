"""Shared step and intent codes, and the shared grade (2026-11-12, Eric; DECISIONS 96).

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-12

Additive only (PRD constraint 16): upgrade() adds one table and two columns; downgrade() removes
only them.
- shared_codes: the code each step (S-01) and intent statement (I1) is shown with, kept per
  engagement and never deleted, so a code survives refresh and republish and is never reused.
- discrepancy_items.grade, gap_findings.grade: the grade Eric chose (confirmed, indicated,
  hypothesis); null while the suggested grade stands.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def upgrade() -> None:
    op.create_table(
        "shared_codes",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("ref_key", sa.Text(), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_shared_codes_engagement_id"), "shared_codes", ["engagement_id"], unique=False
    )
    op.add_column("discrepancy_items", sa.Column("grade", sa.String(length=12), nullable=True))
    op.add_column("gap_findings", sa.Column("grade", sa.String(length=12), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("gap_findings") as batch:
        batch.drop_column("grade")
    with op.batch_alter_table("discrepancy_items") as batch:
        batch.drop_column("grade")
    op.drop_index(op.f("ix_shared_codes_engagement_id"), table_name="shared_codes")
    op.drop_table("shared_codes")
