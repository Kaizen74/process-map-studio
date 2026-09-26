"""Stage prompts and how source text is put in front of Claude (PRD §3.7, §3.8 G1, G2, G9).

Prompts are Markdown files in `app/prompts/`, each starting with a version line
`<!-- prompt: NAME · version N -->`; the version is stored with every AI call. Source text is sent
inside `<source>` and `<segment>` tags so the prompts can say that everything inside the tags is
data to analyse, never instructions (G9). No database access.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from app.domain.models import Prompt, PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_HEADER = re.compile(
    r"^<!--\s*prompt:\s*(?P<name>[\w-]+)\s*·\s*version\s*(?P<version>[\w.-]+)\s*-->\s*\n"
)
_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> Result[Prompt]:
    path = prompts_dir / f"{name}.md"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return Err(ErrorKind.IO, "A stage prompt is missing from the app.", {"prompt": name})
    header = _HEADER.match(raw)
    if header is None or header.group("name") != name:
        return Err(ErrorKind.IO, "A stage prompt has no version line.", {"prompt": name})
    return Ok(Prompt(name=name, version=header.group("version"), text=raw[header.end() :].strip()))


def escape(text: str) -> str:
    """Source text can't close a tag or open a new one (G9)."""
    return text.translate(_ESCAPES)


def render_source(source_ref: str, kind: str, segments: Sequence[PromptSegment]) -> str:
    """One source as tagged data: `<source id kind>` holding one `<segment id anchor [speaker]>`
    per passage. Text is escaped; names are expected to be hidden already (G10)."""
    lines = [f'<source id="{escape(source_ref)}" kind="{escape(kind)}">']
    for segment in segments:
        speaker = f' speaker="{escape(segment.speaker_role)}"' if segment.speaker_role else ""
        lines.append(
            f'<segment id="{escape(segment.ref)}" anchor="{escape(segment.anchor)}"{speaker}>'
            f"{escape(segment.text)}</segment>"
        )
    lines.append("</source>")
    return "\n".join(lines)


def cited_text(segments: Sequence[PromptSegment]) -> str:
    """The text a claim may be checked against: each passage exactly as sent (escaped), with the
    speaker's role in front of transcript turns so G5 can find the role."""
    return "\n".join(
        f"{escape(s.speaker_role)}: {escape(s.text)}" if s.speaker_role else escape(s.text)
        for s in segments
    )
