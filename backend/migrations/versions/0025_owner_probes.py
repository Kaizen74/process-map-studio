"""Eric's own suggested probes for interviews (2026-11-26, Eric; DECISIONS 113).

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-26

Additive only (PRD constraint 16): upgrade() adds the owner_probes table (a probe Eric types or
pastes from his desk research, with an optional note of what it is about); downgrade() removes
only it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def upgrade() -> None:
    op.create_table(
        "owner_probes",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("about", sa.Text(), nullable=False),
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_owner_probes_engagement_id"), "owner_probes", ["engagement_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_owner_probes_engagement_id"), table_name="owner_probes")
    op.drop_table("owner_probes")
