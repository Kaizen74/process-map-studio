"""Architecture test (PRD §3.2): parses imports with ast and enforces the layer rules.

- services/ never imports db, repositories, actions, pipeline or routers
- routers/ never imports repositories, services, db or pipeline (they call actions)
- only services/ai_service.py imports the anthropic SDK
- domain/ imports no other app layer
- repositories/ never import actions, pipeline, routers or services (dependency flows downward)
- actions/ and pipeline/ never import routers
- only repositories/ import the table definitions (app.repositories.tables)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.paths import BACKEND_ROOT

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "services": ("app.db", "app.repositories", "app.actions", "app.pipeline", "app.routers"),
    "routers": ("app.repositories", "app.services", "app.db", "app.pipeline"),
    "repositories": ("app.actions", "app.pipeline", "app.routers", "app.services"),
    "actions": ("app.routers",),
    "pipeline": ("app.routers",),
}
AI_SDK = "anthropic"
TABLES = "app.repositories.tables"
AI_SERVICE = "app.services.ai_service"


def module_name(app_root: Path, path: Path) -> str:
    rel = path.relative_to(app_root.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(path: Path, module: str) -> list[str]:
    """Absolute names of everything a file imports (relative imports resolved)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    is_package = path.name == "__init__.py"
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.split(".")
                drop = node.level - 1 if is_package else node.level
                base = base[: len(base) - drop] if drop else base
                prefix = ".".join(base)
                target = f"{prefix}.{node.module}" if node.module else prefix
            else:
                target = node.module or ""
            names.append(target)
            names += [f"{target}.{alias.name}" for alias in node.names]
    return names


def matches(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def find_violations(app_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(app_root.rglob("*.py")):
        module = module_name(app_root, path)
        layer = module.split(".")[1] if module.count(".") >= 1 else ""
        for name in imported_modules(path, module):
            if matches(name, AI_SDK) and module != AI_SERVICE:
                violations.append(f"{module} imports {name}: only {AI_SERVICE} may use the SDK")
            if layer == "domain" and matches(name, "app") and not matches(name, "app.domain"):
                violations.append(f"{module} imports {name}: domain imports no other app layer")
            if matches(name, TABLES) and layer != "repositories":
                violations.append(f"{module} imports {name}: only repositories use the tables")
            for forbidden in FORBIDDEN.get(layer, ()):
                if matches(name, forbidden):
                    violations.append(f"{module} imports {name}: {layer} must not use {forbidden}")
    return sorted(set(violations))


def test_backend_respects_layer_rules() -> None:
    assert find_violations(BACKEND_ROOT / "app") == []


def test_all_layers_exist() -> None:
    app_root = BACKEND_ROOT / "app"
    for layer in ("domain", "routers", "actions", "pipeline", "services", "repositories"):
        assert (app_root / layer / "__init__.py").is_file(), f"missing layer {layer}"


def write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    ("rel", "source", "expected"),
    [
        ("services/parsing.py", "from app import db\n", "services must not use app.db"),
        ("services/lint.py", "from app.repositories import x\n", "must not use app.repositories"),
        ("services/quality.py", "from ..actions import review\n", "must not use app.actions"),
        ("routers/sources.py", "import app.services.parsing\n", "must not use app.services"),
        ("routers/review.py", "from app.repositories.elements import get\n", "routers must not"),
        ("actions/review.py", "import anthropic\n", "only app.services.ai_service may use"),
        ("services/layout.py", "from anthropic import Anthropic\n", "only app.services.ai_service"),
        ("domain/models.py", "from app.services import grounding\n", "domain imports no other"),
        ("domain/enums.py", "from ..actions import x\n", "domain imports no other"),
        ("repositories/jobs.py", "from app.actions import publish\n", "must not use app.actions"),
        ("actions/publish.py", "from app.routers import review\n", "must not use app.routers"),
        ("actions/review.py", "from app.repositories.tables import Element\n", "only repositories"),
        ("services/lint.py", "from app.repositories import tables\n", "only repositories"),
    ],
)
def test_checker_catches_violations(tmp_path: Path, rel: str, source: str, expected: str) -> None:
    app_root = tmp_path / "app"
    write(app_root, "__init__.py", "")
    write(app_root, rel, source)
    violations = find_violations(app_root)
    assert any(expected in v for v in violations), violations


def test_checker_allows_legal_imports(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    write(app_root, "__init__.py", "")
    write(app_root, "services/ai_service.py", "import anthropic\nfrom app.domain import result\n")
    write(app_root, "routers/review.py", "from app.actions import review\n")
    write(app_root, "actions/review.py", "from app.services import lint\nfrom app import db\n")
    write(app_root, "repositories/elements.py", "from app import db\nfrom app.domain import x\n")
    write(app_root, "domain/models.py", "from .result import Ok\nfrom pydantic import BaseModel\n")
    assert find_violations(app_root) == []
