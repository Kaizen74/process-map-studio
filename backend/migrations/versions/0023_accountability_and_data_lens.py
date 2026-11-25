"""Decision rights, SOP owners, process owner and the data lens (2026-11-25, Eric; DECISIONS 110,
PRD §3.20).

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-25

Additive only (PRD constraint 16): upgrade() adds columns; downgrade() removes only them.
- elements: the decider named in the documents (status, role, passage) and the system of record
  (status, role, other system's name).
- edges: how the data moves at a handoff (B.57; null = not known).
- sources: the SOP's owner role (and whether a free-text owner was checked), the role that
  updates it, its review dates, and whether the controlled copy flag was set by Eric.
- engagements: the process owner (a role, or another role's name).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def _role(batch: object, table: str, column: str) -> None:
    batch.add_column(sa.Column(column, ID, nullable=True))  # type: ignore[attr-defined]
    batch.create_index(f"ix_{table}_{column}", [column])  # type: ignore[attr-defined]
    batch.create_foreign_key(  # type: ignore[attr-defined]
        f"fk_{table}_{column}", "roles", [column], ["id"], ondelete="SET NULL"
    )


def upgrade() -> None:
    with op.batch_alter_table("elements") as batch:
        batch.add_column(sa.Column("paper_decider_status", sa.String(length=16), nullable=True))
        _role(batch, "elements", "paper_decider_role_id")
        batch.add_column(sa.Column("paper_decider_segment_id", ID, nullable=True))
        batch.add_column(sa.Column("system_status", sa.String(length=16), nullable=True))
        _role(batch, "elements", "system_role_id")
        batch.add_column(sa.Column("system_other", sa.Text(), nullable=True))
    with op.batch_alter_table("edges") as batch:
        batch.add_column(sa.Column("data_move", sa.String(length=24), nullable=True))
    with op.batch_alter_table("sources") as batch:
        _role(batch, "sources", "owner_role_id")
        batch.add_column(
            sa.Column("owner_checked", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        _role(batch, "sources", "updated_by_role_id")
        batch.add_column(
            sa.Column("updated_by_other", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("last_reviewed", sa.String(length=32), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("review_due", sa.String(length=32), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "controlled_copy_set", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
    with op.batch_alter_table("engagements") as batch:
        # No foreign key: roles already point at engagements, so none back (no cycle).
        batch.add_column(sa.Column("process_owner_role_id", ID, nullable=True))
        batch.add_column(
            sa.Column("process_owner_other", sa.Text(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.drop_column("process_owner_other")
        batch.drop_column("process_owner_role_id")
    with op.batch_alter_table("sources") as batch:
        for column in ("owner_role_id", "updated_by_role_id"):
            batch.drop_constraint(f"fk_sources_{column}", type_="foreignkey")
            batch.drop_index(f"ix_sources_{column}")
        for column in (
            "controlled_copy_set", "review_due", "last_reviewed", "updated_by_other",
            "updated_by_role_id", "owner_checked", "owner_role_id",
        ):  # fmt: skip
            batch.drop_column(column)
    with op.batch_alter_table("edges") as batch:
        batch.drop_column("data_move")
    with op.batch_alter_table("elements") as batch:
        for column in ("paper_decider_role_id", "system_role_id"):
            batch.drop_constraint(f"fk_elements_{column}", type_="foreignkey")
            batch.drop_index(f"ix_elements_{column}")
        for column in (
            "system_other", "system_role_id", "system_status", "paper_decider_segment_id",
            "paper_decider_role_id", "paper_decider_status",
        ):  # fmt: skip
            batch.drop_column(column)
