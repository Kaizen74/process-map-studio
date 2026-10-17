"""PRD v1.12 data model: intent and the Reality views (§3.5, §3.16-3.18; phase P13a, 2026-10-13).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-13

Additive only (PRD constraint 16): upgrade() adds four tables; downgrade() drops only them. The
source kind `policy_or_charter` (B.1) is a value, not a column, so it needs no migration.
- intent_statements: what the organisation intends, quoted from a policy or charter (with its
  segments and verification) or stated by an owner (role and date).
- intent_conflicts: design gaps proposed by IX_compare, quoting both sides, until Eric confirms.
- discrepancy_items: each discrepancy's persistent X code, title and Eric's verdict.
- reality_snapshots: one snapshot per version, frozen on publish (filled from P13b).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

ID = sa.String(length=36)


def _row_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    ]


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="CASCADE")


def _set_null(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "intent_statements",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("element_stable_key", sa.Text(), nullable=True),
        sa.Column("phase_name", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metric", sa.String(length=24), nullable=True),
        sa.Column("comparator", sa.String(length=16), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=8), nullable=True),
        sa.Column("source_id", ID, nullable=True),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("owner_role_id", ID, nullable=True),
        sa.Column("stated_on", sa.String(length=32), nullable=True),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("rejection_guardrail", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        _fk("source_id", "sources.id"),
        _set_null("owner_role_id", "roles.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "intent_conflicts",
        sa.Column("version_id", ID, nullable=False),
        sa.Column("intent_id", ID, nullable=False),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("intent_quote", sa.Text(), nullable=False),
        sa.Column("conflict_text", sa.Text(), nullable=False),
        sa.Column("verifier_verdict", sa.String(length=16), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("version_id", "map_versions.id"),
        _fk("intent_id", "intent_statements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "discrepancy_items",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("location_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("first_version_id", ID, nullable=True),
        sa.Column("verdict_decided", sa.String(length=16), nullable=True),
        sa.Column("verdict_note", sa.Text(), nullable=False),
        sa.Column("decision_owner_role_id", ID, nullable=True),
        sa.Column("retired", sa.Boolean(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        _set_null("first_version_id", "map_versions.id"),
        _set_null("decision_owner_role_id", "roles.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reality_snapshots",
        sa.Column("version_id", ID, nullable=False),
        sa.Column("view", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.Column("rules_version", sa.String(length=16), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=False),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        *_row_columns(),
        _fk("version_id", "map_versions.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for table, column in INDEXED:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


# Every foreign-key column of the new tables is indexed, as the tables module declares.
INDEXED = [
    ("intent_statements", "engagement_id"),
    ("intent_statements", "source_id"),
    ("intent_statements", "owner_role_id"),
    ("intent_conflicts", "version_id"),
    ("intent_conflicts", "intent_id"),
    ("discrepancy_items", "engagement_id"),
    ("discrepancy_items", "first_version_id"),
    ("discrepancy_items", "decision_owner_role_id"),
    ("reality_snapshots", "version_id"),
]
NEW_TABLES = ["reality_snapshots", "discrepancy_items", "intent_conflicts", "intent_statements"]


def downgrade() -> None:
    for table, column in INDEXED:
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    for table in NEW_TABLES:
        op.drop_table(table)
