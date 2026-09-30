"""How each draft was made: the run record (anti-drift guardrail, 2026-09-30).

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-30

Additive only (PRD constraint 16): upgrade() adds one nullable column; downgrade() removes only it.
- map_versions.run_record: the model, effort, verifier and instruction versions a draft or refresh
  was made with (API_CONTRACT → Run record), so a later refresh can say what would differ. Drafts
  made earlier keep `NULL`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("map_versions", sa.Column("run_record", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("map_versions") as batch:
        batch.drop_column("run_record")
