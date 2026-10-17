"""A published version's system-trace evidence, frozen at publishing (P10b R5b, 2026-10-07).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-07

Additive only (PRD constraint 16): upgrade() adds one nullable column; downgrade() removes only it.
- map_versions.system_traces: the system-trace evidence of each step (log, window, cases, figures;
  never a quote or a user ID) as the draft showed it when it was published, so a published version
  never changes when the alignment does. Drafts keep `NULL` (theirs is worked out on every read).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("map_versions", sa.Column("system_traces", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("map_versions") as batch:
        batch.drop_column("system_traces")
