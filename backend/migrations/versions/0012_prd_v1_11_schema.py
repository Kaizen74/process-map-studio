"""PRD v1.11 data model: system records, value calculator and step disposition (§3.5, §3.13-3.15).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-05

Additive only (PRD constraint 16): upgrade() adds seven tables and six nullable columns on
`elements`; downgrade() removes only those. As with 0009, the database holds every §3.5 table from
the start; phase P10b fills them, so nothing reads or writes these yet.
`events` has no resource or user column by design (constraint 24: user IDs from a system log are
converted to roles during import and never stored).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ID = sa.String(length=36)

# New nullable columns on `elements`: (column, type).
COLUMNS: list[tuple[str, sa.types.TypeEngine[object]]] = [
    ("disposition", sa.String(length=16)),
    ("disposition_suggested", sa.String(length=16)),
    ("disposition_reason", sa.Text()),
    ("risk_flag", sa.String(length=16)),
    ("time_override_min", sa.Float()),
    ("volume_override_month", sa.Float()),
]


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
    with op.batch_alter_table("elements") as batch:
        for column, kind in COLUMNS:
            batch.add_column(sa.Column(column, kind, nullable=True))
    op.create_table(
        "event_logs",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("system", sa.Text(), nullable=False),
        sa.Column("file_ref", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.String(length=32), nullable=True),
        sa.Column("window_end", sa.String(length=32), nullable=True),
        sa.Column("column_map", sa.JSON(), nullable=False),
        sa.Column("validation_report", sa.JSON(), nullable=False),
        sa.Column("approved_by_role", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("log_id", ID, nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("activity", sa.Text(), nullable=False),
        sa.Column("ts_start", sa.String(length=32), nullable=False),
        sa.Column("ts_end", sa.String(length=32), nullable=True),
        sa.Column("role_id", ID, nullable=True),
        sa.Column("case_attributes", sa.JSON(), nullable=False),
        *_row_columns(),
        _fk("log_id", "event_logs.id"),
        _set_null("role_id", "roles.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "case_key_maps",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("from_log_id", ID, nullable=False),
        sa.Column("to_log_id", ID, nullable=False),
        sa.Column("from_case_id", sa.Text(), nullable=False),
        sa.Column("to_case_id", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        _fk("from_log_id", "event_logs.id"),
        _fk("to_log_id", "event_logs.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "activity_alignment",
        sa.Column("log_id", ID, nullable=False),
        sa.Column("activity", sa.Text(), nullable=False),
        sa.Column("element_id", ID, nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.String(length=32), nullable=True),
        *_row_columns(),
        _fk("log_id", "event_logs.id"),
        _set_null("element_id", "elements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mining_metrics",
        sa.Column("log_id", ID, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        *_row_columns(),
        _fk("log_id", "event_logs.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "role_costs",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("role_id", ID, nullable=False),
        sa.Column("hourly_cost", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        _fk("role_id", "roles.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "value_assumptions",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("reduction_pct", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for table, column in INDEXED:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


# Every foreign-key column of the new tables is indexed, as the tables module declares.
INDEXED = [
    ("event_logs", "engagement_id"),
    ("events", "log_id"),
    ("events", "role_id"),
    ("case_key_maps", "engagement_id"),
    ("case_key_maps", "from_log_id"),
    ("case_key_maps", "to_log_id"),
    ("activity_alignment", "log_id"),
    ("activity_alignment", "element_id"),
    ("mining_metrics", "log_id"),
    ("role_costs", "engagement_id"),
    ("role_costs", "role_id"),
    ("value_assumptions", "engagement_id"),
]
NEW_TABLES = [
    "value_assumptions",
    "role_costs",
    "mining_metrics",
    "activity_alignment",
    "case_key_maps",
    "events",
    "event_logs",
]


def downgrade() -> None:
    for table, column in INDEXED:
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    for table in NEW_TABLES:
        op.drop_table(table)
    with op.batch_alter_table("elements") as batch:
        for column, _kind in COLUMNS:
            batch.drop_column(column)
