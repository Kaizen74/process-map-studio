"""Database set-up (PRD §3.1, §3.5): SQLite file data/app.db, sessions and migrations.

Only repositories run queries; actions open sessions (units of work) with `session_scope`.
Migrations are Alembic scripts in backend/migrations; they are additive only (constraint 16).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
DB_FILENAME = "app.db"


def db_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def make_engine(path: Path) -> Engine:
    """A SQLite engine with foreign keys enforced (so deletes cascade) and deleted content
    overwritten: SQLite otherwise keeps deleted rows in free pages, where a deleted client's
    interview could still be read from the file. Some SQLite builds do this by default, others
    don't, so it is set here (deep review, 2026-10-19)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA secure_delete=ON")
        cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One unit of work: commit on success, roll back on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _alembic_config(path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def pending_migrations(path: Path) -> int:
    """How many migrations are waiting (all of them for a database that doesn't exist yet)."""
    script = ScriptDirectory.from_config(_alembic_config(path))
    heads = set(script.get_heads())
    if not path.exists():
        return len(list(script.walk_revisions()))
    engine = make_engine(path)
    try:
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()
    if current == heads:
        return 0
    lower = tuple(current) if current else None
    return len(list(script.iterate_revisions(tuple(heads), lower)))


def upgrade(path: Path) -> None:
    """Apply every waiting migration (creates the database file if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_alembic_config(path), "head")


def downgrade(path: Path, revision: str) -> None:
    """Developers and tests only: step back to a revision."""
    command.downgrade(_alembic_config(path), revision)
