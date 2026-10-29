"""Questions about another flow (2026-10-29, Eric; DECISIONS 83).

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-29

Additive only (PRD constraint 16): upgrade() adds one column; downgrade() removes only it.
- unknowns.outside_flow: on a one-flow map whose drafting set claims about other flows aside, an
  open question from the reading that points only at passages no step of the map uses. It is
  listed under Review → Outside this flow instead of becoming one of the map's questions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "unknowns",
        sa.Column("outside_flow", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("unknowns") as batch:
        batch.drop_column("outside_flow")
