"""Database maintenance commands used by scripts/start.py (PRD §3.1).

    python -m app.manage pending-migrations   # prints how many database updates are waiting
    python -m app.manage upgrade              # applies them (additive only, PRD constraint 16)

Start backs up data/app.db before running `upgrade` whenever updates are waiting.
"""

from __future__ import annotations

import argparse
import sys

from app import db
from app.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    parser.add_argument("command", choices=["pending-migrations", "upgrade"])
    args = parser.parse_args(argv)
    path = db.db_path(load_config().data_dir)
    if args.command == "pending-migrations":
        print(db.pending_migrations(path))
    else:
        db.upgrade(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
