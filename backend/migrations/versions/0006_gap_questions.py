"""Causes a gap analysis can't explain, kept as suggested SME questions (phase P10).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28

Additive only (PRD constraint 16): upgrade() adds one column; downgrade() removes only it.
- gap_findings.question: for a cause the sources don't explain (PRD §3.11.1 step 2, A.7 "Likely
  cause of the approval gap"), the question to ask the SMEs instead of a guess; empty for findings.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gap_findings",
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("gap_findings") as batch:
        batch.drop_column("question")
