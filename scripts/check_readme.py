"""README check (PRD section 3.10 and Appendix D). Standard library only.

Fails if README.md is missing a required Appendix D heading, still contains a
{{placeholder}}, or links to a local file that doesn't exist.
Exit codes: 0 = pass, 1 = fail.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Headings exactly as written in PRD Appendix D (a unit test keeps this list in sync with the PRD).
REQUIRED_HEADINGS = [
    "# Process Map Studio",
    "## What you need",
    "## One-time setup",
    "### 1. Install the three free tools",
    "### 2. Get the app onto your computer",
    "### 3. Run setup (one time, and again after each update)",
    "### 4. Get your Claude API key",
    "### 5. First start",
    "## Everyday use",
    "## Update to the latest version",
    "## Install on another computer",
    "## Back up and restore your work",
    "## What is never uploaded to GitHub",
    "## If something goes wrong",
    "## For builders",
]

PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def check_readme(readme: Path) -> list[str]:
    if not readme.is_file():
        return ["README.md is missing."]
    text = readme.read_text(encoding="utf-8")
    lines = {line.rstrip() for line in text.splitlines()}
    problems = [f'missing heading "{h}"' for h in REQUIRED_HEADINGS if h not in lines]
    problems += [f"placeholder left in: {m}" for m in sorted(set(PLACEHOLDER.findall(text)))]
    for target in sorted(set(LINK.findall(text))):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
            continue
        local = target.split("#", 1)[0]
        if local and not (readme.parent / local).exists():
            problems.append(f"broken link to {target}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    readme = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "README.md"
    problems = check_readme(readme)
    if problems:
        print("FAIL README check:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS README check: all required sections present, no placeholders, links work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
