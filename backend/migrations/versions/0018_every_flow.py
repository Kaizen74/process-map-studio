"""Map one flow or every flow in the documents (2026-10-28, Eric's cargo manual; DECISIONS 81).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-28

Additive only (PRD constraint 16): upgrade() adds one column; downgrade() removes only it.
- engagements.every_flow: ticked by Eric on the scope card for an overview of every flow the
  documents describe. Unticked (the default), drafting builds only the engagement's own flow, from
  its trigger to its end point, and sets claims about other flows aside (claims.verification_status
  `outside_flow`, B.18), listed under Review → Outside this flow.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "engagements",
        sa.Column("every_flow", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.drop_column("every_flow")
