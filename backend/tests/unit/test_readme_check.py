"""README check (PRD §3.10, Appendix D)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from tests.paths import REPO_ROOT, SCRIPTS_DIR


def load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_readme", SCRIPTS_DIR / "check_readme.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_checker()


def minimal_readme(tmp_path: Path, extra: str = "") -> Path:
    body = "\n\n".join(checker.REQUIRED_HEADINGS) + "\n" + extra
    readme = tmp_path / "README.md"
    readme.write_text(body, encoding="utf-8")
    return readme


def test_real_readme_passes() -> None:
    assert checker.check_readme(REPO_ROOT / "README.md") == []


def test_heading_list_matches_prd_appendix_d() -> None:
    prd = (REPO_ROOT / "PRD_ProcessMapStudio.md").read_text(encoding="utf-8")
    template = prd.split("**D.1 Required content**", 1)[1].split("````markdown", 1)[1]
    template = template.split("````", 1)[0]
    prd_headings = [line for line in template.splitlines() if re.match(r"^#{1,3} ", line)]
    assert prd_headings == checker.REQUIRED_HEADINGS


def test_missing_heading_fails(tmp_path: Path) -> None:
    readme = minimal_readme(tmp_path)
    readme.write_text(readme.read_text().replace("## Everyday use\n", ""), encoding="utf-8")
    assert checker.check_readme(readme) == ['missing heading "## Everyday use"']


def test_placeholder_fails(tmp_path: Path) -> None:
    readme = minimal_readme(tmp_path, "Version {{version}}\n")
    assert checker.check_readme(readme) == ["placeholder left in: {{version}}"]


def test_broken_local_link_fails_and_web_links_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "GUIDE.md").write_text("guide")
    readme = minimal_readme(
        tmp_path,
        "[ok](GUIDE.md) [anchor](GUIDE.md#top) [web](https://example.com) "
        "[x](#here) [bad](NOPE.md)\n",
    )
    assert checker.check_readme(readme) == ["broken link to NOPE.md"]


def test_missing_readme_fails(tmp_path: Path) -> None:
    assert checker.check_readme(tmp_path / "README.md") == ["README.md is missing."]


def test_main_exit_codes(tmp_path: Path) -> None:
    assert checker.main([str(REPO_ROOT / "README.md")]) == 0
    assert checker.main([str(tmp_path / "README.md")]) == 1
