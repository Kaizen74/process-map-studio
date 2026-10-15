"""Whether the process starts or ends outside the organisation (E1, 2026-10-15; Eric's decision).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-15

Additive only (PRD constraint 16): upgrade() adds two columns; downgrade() removes only them.
- engagements.trigger_external, engagements.end_point_external: ticked by Eric on the scope card;
  the Reality views' Typical case (RV7) draws an "Outside the organisation" lane when either is
  set (PRD §3.18.3), never guessing it from the scope card's words (DECISIONS 47, 51).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

COLUMNS = ("trigger_external", "end_point_external")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(
            "engagements",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        for name in reversed(COLUMNS):
            batch.drop_column(name)
