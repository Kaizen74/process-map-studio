"""A lane's Capability Compass role and what checks a handoff (2026-11-26, Eric; DECISIONS 113).

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-26

Additive only (PRD constraint 16): upgrade() adds roles.compass_role_ref (the hand-off role, such
as RL-014, this lane is; null when not linked) and edges.data_check (one line on what checks the
data at a handoff; "" when not recorded); downgrade() removes only them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roles") as batch:
        batch.add_column(sa.Column("compass_role_ref", sa.String(length=32), nullable=True))
    with op.batch_alter_table("edges") as batch:
        batch.add_column(sa.Column("data_check", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("edges") as batch:
        batch.drop_column("data_check")
    with op.batch_alter_table("roles") as batch:
        batch.drop_column("compass_role_ref")
