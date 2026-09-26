"""PRD constraint 19: no AGPL or GPL dependencies (Python and frontend packages)."""

from __future__ import annotations

import json
import re
from importlib.metadata import distributions

import pytest

from tests.paths import FRONTEND_ROOT

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


def node_package_licence(package_json: dict[str, object]) -> str:
    """Read the licence from a package.json in any of its historical forms."""
    lic = package_json.get("license") or package_json.get("licenses")
    if isinstance(lic, dict):
        return str(lic.get("type", ""))
    if isinstance(lic, list):
        return " OR ".join(str(x.get("type", x)) if isinstance(x, dict) else str(x) for x in lic)
    return str(lic or "")


def test_no_gpl_frontend_packages_installed() -> None:
    node_modules = FRONTEND_ROOT / "node_modules"
    if not node_modules.is_dir():
        pytest.skip("frontend packages not installed yet (run setup)")
    offenders = []
    checked = 0
    for package_json in node_modules.rglob("package.json"):
        parts = package_json.parent.parts
        is_root = parts[-2] == "node_modules" or (
            len(parts) > 2 and parts[-3] == "node_modules" and parts[-2].startswith("@")
        )
        if not is_root:
            continue
        data = json.loads(package_json.read_text(encoding="utf-8"))
        licence = node_package_licence(data)
        checked += 1
        if COPYLEFT.search(licence):
            offenders.append(f"{data.get('name')}: {licence}")
    assert checked > 0
    assert offenders == [], "GPL-family packages are not allowed: " + "; ".join(offenders)
