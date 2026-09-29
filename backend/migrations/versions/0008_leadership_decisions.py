"""Eric's "Decision needed" lines on the leadership view (phase P11).

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-29

Additive only (PRD constraint 16): upgrade() adds one table; downgrade() removes only it.
- leadership_decisions: one line per systemic cause type of a version (PRD §4 Views,
  `PUT /versions/{vid}/leadership/decisions`, §5.4 Leadership). Eric's notes about the map, not map
  content, so a published version can carry them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leadership_decisions",
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("cause_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["map_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_leadership_decisions_version_id"),
        "leadership_decisions",
        ["version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_leadership_decisions_version_id"), table_name="leadership_decisions")
    op.drop_table("leadership_decisions")
