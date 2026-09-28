"""The steps behind each merge proposal (phase P6).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27

Additive only (PRD constraint 16): upgrade() adds one column; downgrade() removes only it.
- merge_proposals.claim_groups: the steps a proposal would merge, as S2 drafted them (label, kind,
  lane role and claim IDs of each), so the Merge tab can show them side by side and Split can
  put back the separate steps of a merge made at 0.80 or above (PRD §5.7.10, §9 assumption 8).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merge_proposals",
        sa.Column("claim_groups", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    with op.batch_alter_table("merge_proposals") as batch:
        batch.drop_column("claim_groups")
