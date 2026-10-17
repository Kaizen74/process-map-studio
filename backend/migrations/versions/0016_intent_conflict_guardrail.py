"""Why a design-gap proposal was turned down (P13a-2, 2026-10-13).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-13

Additive only (PRD constraint 16): upgrade() adds one nullable column; downgrade() removes only it.
- intent_conflicts.rejection_guardrail: the check (B.20, for example IX1 or IXV) that turned an
  `IX_compare` proposal down, so Eric sees what was rejected and why (G16, trap RT8).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intent_conflicts", sa.Column("rejection_guardrail", sa.String(length=8), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("intent_conflicts") as batch:
        batch.drop_column("rejection_guardrail")
