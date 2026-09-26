"""PRD constraint 19: no AGPL or GPL dependencies (Python side)."""

from __future__ import annotations

import re
from importlib.metadata import distributions

# Matches GPL, LGPL, AGPL and "General Public License" in any licence field or classifier.
COPYLEFT = re.compile(r"\b(A|L)?GPL\b|General Public License", re.IGNORECASE)


def licence_text(dist_name: str, fields: list[str]) -> str:
    return f"{dist_name}: " + " | ".join(fields)


def test_no_gpl_python_packages_installed() -> None:
    offenders = []
    for dist in distributions():
        meta = dist.metadata
        fields = [meta.get("License-Expression") or "", meta.get("License") or ""]
        fields += [c for c in (meta.get_all("Classifier") or []) if c.startswith("License")]
        # Some packages put the full licence text in "License"; check only its first line.
        fields = [f.splitlines()[0] if f else "" for f in fields]
        if any(COPYLEFT.search(f) for f in fields):
            offenders.append(licence_text(meta["Name"], fields))
    assert offenders == [], "GPL-family packages are not allowed: " + "; ".join(offenders)
