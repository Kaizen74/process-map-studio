"""An SOP's own title (2026-11-25, Eric; DECISIONS 110, PRD §3.20).

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-25

Additive only (PRD constraint 16): upgrade() adds sources.title (the document's own title, ""
when not typed: the file name stands in); downgrade() removes only it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("title", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("title")
