"""Draft job stages (phase P3).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

Additive only (PRD constraint 16): upgrade() adds one column; downgrade() removes only that.
- jobs.stages: for "draft" jobs, each stage's name, status and start and finish times, so the
  Draft screen can show the stage stepper with elapsed times after a reload.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("stages", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("stages")
