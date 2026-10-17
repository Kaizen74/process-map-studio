"""Eric's notes on a step's disposition and on his value overrides (P10b R9, 2026-10-08).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-08

Additive only (PRD constraint 16): upgrade() adds two nullable columns; downgrade() removes only
them.
- elements.disposition_note: why Eric chose the step's disposition (§3.15; audited as well).
- elements.value_override_note: the note his time or volume override needs (§3.14: "Eric's
  override (R, with a note)").
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("elements", sa.Column("disposition_note", sa.Text(), nullable=True))
    op.add_column("elements", sa.Column("value_override_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("elements") as batch:
        batch.drop_column("value_override_note")
        batch.drop_column("disposition_note")
