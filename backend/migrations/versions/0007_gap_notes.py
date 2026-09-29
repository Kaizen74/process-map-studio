"""Plain-language notes on gap analyses and their findings (phase P10).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-28

Additive only (PRD constraint 16): upgrade() adds two columns; downgrade() removes only them.
- gap_analyses.notes: about the run, e.g. a web search tool error kept as a partial result (TE6)
  or a practice left out as "not a gap" (TE9).
- gap_findings.notes: flags on one finding, e.g. a link to a step not on the map removed (GX6,
  TE7) or the compliance note on a legal or regulatory finding (PRD §3.11.2 step 6).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gap_analyses", sa.Column("notes", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "gap_findings", sa.Column("notes", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade() -> None:
    with op.batch_alter_table("gap_findings") as batch:
        batch.drop_column("notes")
    with op.batch_alter_table("gap_analyses") as batch:
        batch.drop_column("notes")
