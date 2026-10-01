"""PRD v1.10 data model: the tables and columns of the sensemaking framework (§3.12).

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-30

Additive only (PRD constraint 16): upgrade() adds eight tables and new nullable columns on seven
existing tables; downgrade() removes only those. PRD v1.10 §6.3 P1 has the database hold every
§3.5 table from the start; the phases that fill them (P4b translation core, P4c sensemaking and
interview tools) come later, so nothing reads or writes these yet.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

ID = sa.String(length=36)

# New nullable columns on existing tables: (table, column, type).
COLUMNS: list[tuple[str, str, sa.types.TypeEngine[object]]] = [
    ("engagements", "conventions", sa.JSON()),
    ("source_segments", "question_id", sa.String(length=16)),
    ("source_segments", "answer_block_id", ID),
    ("source_segments", "marker_tags", sa.JSON()),
    ("claims", "account_type", sa.String(length=16)),
    ("map_versions", "codebook_version", sa.String(length=32)),
    ("elements", "work_type", sa.String(length=16)),
    ("elements", "constraint_type", sa.String(length=16)),
    ("elements", "work_type_basis", sa.JSON()),
    ("elements", "sme_work_type_signifier", sa.Text()),
    ("elements", "work_type_status", sa.String(length=16)),
    ("elements", "practice_described", sa.Boolean()),
    ("elements", "view_membership", sa.String(length=16)),
    ("elements", "variants", sa.JSON()),
    ("elements", "level", sa.String(length=16)),
    ("elements", "parent_element_id", ID),
    ("edges", "sequence_basis", sa.String(length=16)),
    ("edges", "typical", sa.Boolean()),
    ("edges", "view_membership", sa.String(length=16)),
    ("edges", "information_payload", sa.Text()),
    ("gap_findings", "gap_class", sa.String(length=24)),
]


def _row_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", ID, nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    ]


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="CASCADE")


def upgrade() -> None:
    for table, column, kind in COLUMNS:
        op.add_column(table, sa.Column(column, kind, nullable=True))
    op.create_table(
        "fragments",
        sa.Column("version_id", ID, nullable=False),
        sa.Column("source_id", ID, nullable=True),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("fragment_type", sa.String(length=16), nullable=False),
        sa.Column("sme_signifiers", sa.JSON(), nullable=False),
        sa.Column("element_ids", sa.JSON(), nullable=False),
        sa.Column("single_account", sa.Boolean(), nullable=False),
        sa.Column("provenance", sa.String(length=1), nullable=False),
        *_row_columns(),
        _fk("version_id", "map_versions.id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "knowledge_points",
        sa.Column("element_id", ID, nullable=False),
        sa.Column("kdp_type", sa.String(length=24), nullable=False),
        sa.Column("ashen", sa.JSON(), nullable=False),
        sa.Column("knowledge_risk", sa.String(length=8), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=True),
        sa.Column("information_received", sa.JSON(), nullable=False),
        sa.Column("information_attended", sa.JSON(), nullable=False),
        sa.Column("information_wanted", sa.JSON(), nullable=False),
        sa.Column("communicated_via", sa.JSON(), nullable=False),
        *_row_columns(),
        _fk("element_id", "elements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "glossary_terms",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("plain_meaning", sa.Text(), nullable=False),
        sa.Column("standard_label", sa.Text(), nullable=False),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "emergent_themes",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("version_id", ID, nullable=True),
        sa.Column("theme", sa.Text(), nullable=False),
        sa.Column("fragment_ids", sa.JSON(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.ForeignKeyConstraint(["version_id"], ["map_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "interviewee_profiles",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("role_id", ID, nullable=True),
        sa.Column("stakeholder_group", sa.Text(), nullable=False),
        sa.Column("interview_type", sa.String(length=16), nullable=False),
        sa.Column("referred_by_role", sa.Text(), nullable=False),
        sa.Column("previous_profile_session", ID, nullable=True),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "capability_notes",
        sa.Column("version_id", ID, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("dimension", sa.String(length=24), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("element_ids", sa.JSON(), nullable=False),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.String(length=1), nullable=False),
        sa.Column("cause_type", sa.String(length=32), nullable=True),
        *_row_columns(),
        _fk("version_id", "map_versions.id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "interview_guides",
        sa.Column("engagement_id", ID, nullable=False),
        sa.Column("profile_id", ID, nullable=True),
        sa.Column("interview_type", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=False),
        *_row_columns(),
        _fk("engagement_id", "engagements.id"),
        sa.ForeignKeyConstraint(["profile_id"], ["interviewee_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "coverage_reports",
        sa.Column("version_id", ID, nullable=False),
        sa.Column("source_id", ID, nullable=True),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("follow_up_questions", sa.JSON(), nullable=False),
        *_row_columns(),
        _fk("version_id", "map_versions.id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for table, column in INDEXED:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


# Every foreign-key column of the new tables is indexed, as the tables module declares.
INDEXED = [
    ("fragments", "version_id"),
    ("fragments", "source_id"),
    ("knowledge_points", "element_id"),
    ("glossary_terms", "engagement_id"),
    ("emergent_themes", "engagement_id"),
    ("emergent_themes", "version_id"),
    ("interviewee_profiles", "engagement_id"),
    ("interviewee_profiles", "role_id"),
    ("capability_notes", "version_id"),
    ("interview_guides", "engagement_id"),
    ("interview_guides", "profile_id"),
    ("coverage_reports", "version_id"),
    ("coverage_reports", "source_id"),
]
NEW_TABLES = [
    "coverage_reports",
    "interview_guides",
    "capability_notes",
    "interviewee_profiles",
    "emergent_themes",
    "glossary_terms",
    "knowledge_points",
    "fragments",
]


def downgrade() -> None:
    for table, column in INDEXED:
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    for table in NEW_TABLES:
        op.drop_table(table)
    for table in dict.fromkeys(t for t, _c, _k in COLUMNS):
        with op.batch_alter_table(table) as batch:
            for column in [c for t, c, _k in COLUMNS if t == table]:
                batch.drop_column(column)
