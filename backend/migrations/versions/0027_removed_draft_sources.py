"""The sources a draft was made from that were deleted afterwards (2026-11-27, Eric; DECISIONS 114).

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-27

Additive only (PRD constraint 16): upgrade() adds map_versions.removed_sources (the file names of
sources deleted after the version was drafted from them, so Review can say the draft needs a
refresh; null when none); downgrade() removes only it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("map_versions") as batch:
        batch.add_column(sa.Column("removed_sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("map_versions") as batch:
        batch.drop_column("removed_sources")
