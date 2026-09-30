"""Database foundation (PRD §3.5, constraint 16): migration 0001, enums, cascades, manage."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app import db
from app.domain import enums
from app.repositories import tables
from tests.paths import BACKEND_ROOT, REPO_ROOT

PRD_TABLES = {
    "engagements", "sources", "source_segments", "redaction_terms", "roles", "claims",
    "unknowns", "map_versions", "phases", "elements", "element_claims", "raci", "edges",
    "evidence_links", "constraints", "ai_flags", "merge_proposals", "validation_questions",
    "images", "cause_library", "audit_log", "jobs", "ai_calls", "gap_analyses", "gap_findings",
    "external_sources", "external_citations",
    # PRD v1.10 §3.12 (migration 0009), filled from phases P4b and P4c.
    "fragments", "knowledge_points", "glossary_terms", "emergent_themes", "interviewee_profiles",
    "capability_notes", "interview_guides", "coverage_reports",
}  # fmt: skip
# Tables added after 0001 that the PRD table doesn't list (see DECISIONS.md).
# 0004: the sources each draft was made from; 0008: the leadership view's decision lines.
ADDED_TABLES = {"version_sources", "leadership_decisions"}

MIGRATION_COUNT = len(list((BACKEND_ROOT / "migrations" / "versions").glob("0*.py")))


@pytest.fixture()
def migrated(tmp_path: Path) -> Path:
    path = tmp_path / "app.db"
    db.upgrade(path)
    return path


def table_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows} - {"alembic_version"}


def test_migration_creates_every_prd_table(migrated: Path) -> None:
    assert table_names(migrated) == PRD_TABLES | ADDED_TABLES


def test_prd_columns_are_all_present(migrated: Path) -> None:
    prd = (REPO_ROOT / "PRD_ProcessMapStudio.md").read_text(encoding="utf-8")
    section = prd.split("### 3.5 Data model", 1)[1].split("**Versions and locking:**", 1)[0]
    engine = db.make_engine(migrated)
    inspector = inspect(engine)
    missing = []
    checked = 0
    for line in section.splitlines():
        match = re.match(r"^\| `(\w+)` \| (.+) \|$", line)
        if not match:
            continue
        table, spec = match.groups()
        # Words inside a column's description, e.g. "variants (json: … owner, threshold, time)",
        # are not column names (PRD v1.10 added such lists).
        spec = re.sub(r"\s*\([^()]*(?:\([^()]*\)[^()]*)*\)", "", spec)
        names = re.findall(r"(?:^|, )(\w+)(?= \(|,|$| or| —)", spec)
        columns = {c["name"] for c in inspector.get_columns(table)}
        checked += len(names)
        for name in names:
            if name not in columns and name not in {"or"}:
                missing.append(f"{table}.{name}")
    engine.dispose()
    assert missing == []
    assert checked >= 296  # every PRD v1.10 column is read (guards the parser against skipping)


def test_every_table_has_id_and_created_at(migrated: Path) -> None:
    engine = db.make_engine(migrated)
    inspector = inspect(engine)
    for table in PRD_TABLES:
        columns = {c["name"] for c in inspector.get_columns(table)}
        assert {"id", "created_at"} <= columns, table
    engine.dispose()


def test_migrated_schema_matches_the_tables_module(migrated: Path) -> None:
    engine = db.make_engine(migrated)
    inspector = inspect(engine)
    for table in tables.Base.metadata.sorted_tables:
        live = {c["name"]: c["nullable"] for c in inspector.get_columns(table.name)}
        declared = {c.name: c.nullable for c in table.columns}
        assert live == declared, table.name
    engine.dispose()


def test_downgrade_removes_only_what_0001_added(migrated: Path) -> None:
    with sqlite3.connect(migrated) as conn:
        conn.execute("CREATE TABLE eric_notes (id TEXT)")
    db.downgrade(migrated, "base")
    assert table_names(migrated) == {"eric_notes"}


def test_downgrade_of_0002_removes_only_its_columns(migrated: Path) -> None:
    db.downgrade(migrated, "0001")
    engine = db.make_engine(migrated)
    inspector = inspect(engine)
    segments = {c["name"] for c in inspector.get_columns("source_segments")}
    jobs = {c["name"] for c in inspector.get_columns("jobs")}
    engine.dispose()
    assert "is_interviewer" not in segments and {"speaker_role_id", "instruction_like"} <= segments
    assert "target_id" not in jobs and {"status", "stage"} <= jobs
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0


def test_0002_keeps_existing_segments_and_marks_none_as_interviewer(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db.upgrade(path)
    db.downgrade(path, "0001")
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO engagements (id, created_at, name, process_name, trigger, end_point, "
            "in_scope_roles, out_of_scope, process_kpi, industry, adjacent_industries, status, "
            "updated_at) VALUES ('e', 't', 'E', '', '', '', '[]', '', '', '', '[]', 'active', 't')"
        )
        conn.execute(
            "INSERT INTO sources (id, created_at, engagement_id, kind, filename, stored_path, "
            "mime, format, version_date, owner, controlled_copy, text_status, error, ocr_pages) "
            "VALUES ('s', 't', 'e', 'sop', 'f', 'p', '', 'docx', '', '', 0, 'ready', '', '[]')"
        )
        conn.execute(
            "INSERT INTO source_segments (id, created_at, source_id, seq, speaker_label, page, "
            "section, text, corrected, instruction_like) "
            "VALUES ('g', 't', 's', 1, 'Lead', NULL, '', 'Hello', 0, 0)"
        )
    db.upgrade(path)
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT text, is_interviewer FROM source_segments").fetchone()
    assert row == ("Hello", 0)


def test_migrations_are_additive_only() -> None:
    """Constraint 16: no migration drops or alters existing columns in upgrade()."""
    for script in (BACKEND_ROOT / "migrations" / "versions").glob("*.py"):
        upgrade = script.read_text(encoding="utf-8").split("def downgrade", 1)[0]
        for forbidden in ("drop_table", "drop_column", "alter_column", "drop_index", "DROP "):
            assert forbidden not in upgrade, f"{script.name} upgrade() uses {forbidden}"


def test_pending_counts_then_zero_after_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    assert db.pending_migrations(path) == MIGRATION_COUNT
    db.upgrade(path)
    assert db.pending_migrations(path) == 0
    db.upgrade(path)  # running again changes nothing
    assert db.pending_migrations(path) == 0


def test_an_old_database_reports_its_pending_update(migrated: Path) -> None:
    db.downgrade(migrated, "base")
    assert migrated.exists()
    assert db.pending_migrations(migrated) == MIGRATION_COUNT
    db.upgrade(migrated)
    db.downgrade(migrated, "0001")  # a phase-P1 database
    assert db.pending_migrations(migrated) == MIGRATION_COUNT - 1


def test_downgrade_of_0003_removes_only_job_stages_and_keeps_jobs(migrated: Path) -> None:
    with sqlite3.connect(migrated) as conn:
        conn.execute(
            "INSERT INTO jobs (id, created_at, engagement_id, type, status, stage, progress, "
            "message, error, target_id, stages) "
            "VALUES ('j', 't', NULL, 'read_source', 'done', '', 1.0, 'ok', '', NULL, '[]')"
        )
    db.downgrade(migrated, "0002")
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        kept = conn.execute("SELECT id, message, target_id FROM jobs").fetchall()
    assert "stages" not in columns and {"target_id", "status"} <= columns
    assert kept == [("j", "ok", None)]
    db.upgrade(migrated)
    with sqlite3.connect(migrated) as conn:
        assert conn.execute("SELECT stages FROM jobs").fetchone() == ("[]",)


def test_downgrade_of_0004_removes_only_evidence_quotes_and_version_sources(
    migrated: Path,
) -> None:
    db.downgrade(migrated, "0003")
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(evidence_links)")}
    assert {"quote", "note"}.isdisjoint(columns) and {"stance", "verified"} <= columns
    assert "version_sources" not in table_names(migrated)
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0
    assert "version_sources" in table_names(migrated)


def test_downgrade_of_0005_removes_only_merge_groups(migrated: Path) -> None:
    db.downgrade(migrated, "0004")
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(merge_proposals)")}
    assert "claim_groups" not in columns and {"claim_ids", "decision"} <= columns
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(merge_proposals)")}
    assert "claim_groups" in columns


def test_downgrade_of_0006_removes_only_gap_questions(migrated: Path) -> None:
    db.downgrade(migrated, "0005")
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(gap_findings)")}
    assert "question" not in columns and {"finding_type", "disposition"} <= columns
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(gap_findings)")}
    assert "question" in columns


def test_downgrade_of_0007_removes_only_gap_notes(migrated: Path) -> None:
    db.downgrade(migrated, "0006")
    with sqlite3.connect(migrated) as conn:
        analyses = {row[1] for row in conn.execute("PRAGMA table_info(gap_analyses)")}
        findings = {row[1] for row in conn.execute("PRAGMA table_info(gap_findings)")}
    assert "notes" not in analyses and "notes" not in findings
    assert "question" in findings and "brief" in analyses
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0


def test_downgrade_of_0008_removes_only_leadership_decisions(migrated: Path) -> None:
    db.downgrade(migrated, "0007")
    assert "leadership_decisions" not in table_names(migrated)
    assert "gap_findings" in table_names(migrated)
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0
    assert "leadership_decisions" in table_names(migrated)


def test_downgrade_of_0009_removes_only_the_v1_10_tables_and_columns(migrated: Path) -> None:
    new_tables = {
        "fragments", "knowledge_points", "glossary_terms", "emergent_themes",
        "interviewee_profiles", "capability_notes", "interview_guides", "coverage_reports",
    }  # fmt: skip
    engine = db.make_engine(migrated)
    before = {t: {c["name"] for c in inspect(engine).get_columns(t)} for t in ("elements", "edges")}
    engine.dispose()
    db.downgrade(migrated, "0008")
    assert new_tables.isdisjoint(table_names(migrated))
    engine = db.make_engine(migrated)
    inspector = inspect(engine)
    elements = {c["name"] for c in inspector.get_columns("elements")}
    edges = {c["name"] for c in inspector.get_columns("edges")}
    segments = {c["name"] for c in inspector.get_columns("source_segments")}
    engine.dispose()
    assert before["elements"] - elements == {
        "work_type", "constraint_type", "work_type_basis", "sme_work_type_signifier",
        "work_type_status", "practice_described", "view_membership", "variants", "level",
        "parent_element_id",
    }  # fmt: skip
    assert before["edges"] - edges == {
        "sequence_basis",
        "typical",
        "view_membership",
        "information_payload",
    }
    assert "question_id" not in segments and "is_interviewer" in segments
    assert "leadership_decisions" in table_names(migrated)
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0


def test_downgrade_of_0010_removes_only_the_run_record(migrated: Path) -> None:
    def version_columns() -> set[str]:
        engine = db.make_engine(migrated)
        columns = {c["name"] for c in inspect(engine).get_columns("map_versions")}
        engine.dispose()
        return columns

    before = version_columns()
    db.downgrade(migrated, "0009")
    assert before - version_columns() == {"run_record"}
    assert "codebook_version" in version_columns()
    db.upgrade(migrated)
    assert db.pending_migrations(migrated) == 0
    assert "run_record" in version_columns()


def test_foreign_keys_cascade_from_engagement(migrated: Path) -> None:
    factory = db.session_factory(db.make_engine(migrated))
    with db.session_scope(factory) as session:
        engagement = tables.Engagement(name="Load control")
        session.add(engagement)
        session.flush()
        session.add(tables.Role(engagement_id=engagement.id, name="Load controller"))
        session.add(
            tables.Source(
                engagement_id=engagement.id,
                kind="sop",
                filename="a.docx",
                stored_path="x",
                format="docx",
            )
        )
    with db.session_scope(factory) as session:
        session.delete(session.get(tables.Engagement, engagement.id))
    with sqlite3.connect(migrated) as conn:
        assert conn.execute("SELECT count(*) FROM roles").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM sources").fetchone() == (0,)


def test_session_scope_rolls_back_on_error(migrated: Path) -> None:
    factory = db.session_factory(db.make_engine(migrated))
    with pytest.raises(RuntimeError), db.session_scope(factory) as session:
        session.add(tables.Engagement(name="Not saved"))
        session.flush()
        raise RuntimeError("boom")
    with sqlite3.connect(migrated) as conn:
        assert conn.execute("SELECT count(*) FROM engagements").fetchone() == (0,)


def test_rows_get_uuid_ids_and_utc_timestamps(migrated: Path) -> None:
    factory = db.session_factory(db.make_engine(migrated))
    with db.session_scope(factory) as session:
        engagement = tables.Engagement(name="X")
        session.add(engagement)
    assert re.fullmatch(r"[0-9a-f-]{36}", engagement.id)
    assert engagement.created_at.endswith("+00:00")


# PRD v1.10 values that change what the app does, added with the phase that uses them (logged in
# DECISIONS.md 2026-09-30): the "not described" gap edge (P4b, As done view) and the reality-gap
# finding types that Analysis A may return (P4c). The test checks they are still absent, so each
# is removed from this list when its phase adds it.
PENDING_VALUES = {
    "B.8": {"gap"},
    "B.22": {"known_adaptation", "unknown_rule", "disclosure_gap", "control_gap",
             "constraint_mismatch"},
}  # fmt: skip


def test_enums_match_appendix_b() -> None:
    prd = (REPO_ROOT / "PRD_ProcessMapStudio.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (B\.\d+) \| [^|]+ \| ([^|]+) \|$", prd, re.MULTILINE)
    by_id = {
        (cls.__doc__ or "").split()[0]: cls
        for cls in vars(enums).values()
        if isinstance(cls, type) and issubclass(cls, enums.StrEnum) and cls is not enums.StrEnum
    }
    assert len(rows) == 39 == len(by_id)
    for bid, values in rows:
        expected = [re.sub(r"\s*\(.*?\)", "", v).strip().split()[0] for v in values.split("·")]
        pending = PENDING_VALUES.get(bid, set())
        assert pending <= set(expected), bid  # still in the PRD
        assert [m.value for m in by_id[bid]] == [v for v in expected if v not in pending], bid


def test_manage_reports_and_applies_updates(tmp_path: Path) -> None:
    env = {"DATA_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    run = lambda cmd: subprocess.run(  # noqa: E731
        [sys.executable, "-m", "app.manage", cmd],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert run("pending-migrations").stdout.strip() == str(MIGRATION_COUNT)
    run("upgrade")
    assert (tmp_path / "app.db").exists()
    assert run("pending-migrations").stdout.strip() == "0"
