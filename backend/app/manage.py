"""Database maintenance commands used by scripts/start.py (PRD §3.1).

    python -m app.manage pending-migrations   # prints how many database updates are waiting
    python -m app.manage upgrade              # applies them (additive only, PRD constraint 16)

The database and its first migration (0001) arrive in phase P1 with Alembic; until then
there is never an update waiting.
"""

from __future__ import annotations

import argparse
import sys


def pending_migrations() -> int:
    """Number of database updates waiting to be applied."""
    return 0


def upgrade() -> None:
    """Apply waiting database updates."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    parser.add_argument("command", choices=["pending-migrations", "upgrade"])
    args = parser.parse_args(argv)
    if args.command == "pending-migrations":
        print(pending_migrations())
    else:
        upgrade()
    return 0


if __name__ == "__main__":
    sys.exit(main())
