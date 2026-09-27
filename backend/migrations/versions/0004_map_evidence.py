"""Evidence quotes and the sources of each draft (phase P4).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27

Additive only (PRD constraint 16): upgrade() adds two columns and one table; downgrade() removes
only those.
- evidence_links.quote: the words of the passage a stance cites, so the source viewer can highlight
  exactly them (PRD §5.7.8). Never exported.
- evidence_links.note: the divergence detail of a stance, e.g. "Threshold divergence: 10 min in
  SOP vs up to 15 min in practice" (PRD §5.7.7 Evidence).
- version_sources: which sources a draft was made from, so a source that says nothing about a step
  is shown as silent (constraint 4) and sources added later are not.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_links", sa.Column("quote", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("evidence_links", sa.Column("note", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "version_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["map_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_version_sources_version_id", "version_sources", ["version_id"])
    op.create_index("ix_version_sources_source_id", "version_sources", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_version_sources_source_id", table_name="version_sources")
    op.drop_index("ix_version_sources_version_id", table_name="version_sources")
    op.drop_table("version_sources")
    with op.batch_alter_table("evidence_links") as batch:
        batch.drop_column("note")
        batch.drop_column("quote")
