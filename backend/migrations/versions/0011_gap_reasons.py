"""Reality-gap findings: the SME's stated reason and its cause type (PRD §3.12.7; 2026-10-01, C4b).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-01

Additive only (PRD constraint 16): upgrade() adds two columns; downgrade() removes only them.
- gap_findings.stated_reason: the reason an SME gave for a known adaptation, copied exactly from
  the interview (found there by the grounding gate); "" when none was stated.
- gap_findings.cause_type: the cause type (B.9) the reason maps to; `NULL` without a reason.
The gap class itself (B.32) has its column since 0009.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gap_findings",
        sa.Column("stated_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("gap_findings", sa.Column("cause_type", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("gap_findings") as batch:
        batch.drop_column("cause_type")
        batch.drop_column("stated_reason")
