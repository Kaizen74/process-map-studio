"""Speaker mapping and job targets (phase P2).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26

Additive only (PRD constraint 16): upgrade() adds two columns; downgrade() removes only those.
- source_segments.is_interviewer: the speaker label was mapped to "Interviewer" (not a role, not
  a lane); readiness no longer counts it as unmapped.
- jobs.target_id: what a job works on (for "read_source" jobs, the source ID).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_segments",
        sa.Column("is_interviewer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("jobs", sa.Column("target_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("target_id")
    with op.batch_alter_table("source_segments") as batch:
        batch.drop_column("is_interviewer")
