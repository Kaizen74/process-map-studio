"""Stage prompts and how source text is put in front of Claude (PRD §3.7, §3.8 G1, G2, G9).

Prompts are Markdown files in `app/prompts/`, each starting with a version line
`<!-- prompt: NAME · version N -->`; the version is stored with every AI call. Source text is sent
inside `<source>` and `<segment>` tags so the prompts can say that everything inside the tags is
data to analyse, never instructions (G9). No database access.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from app.domain.interview import BankQuestion
from app.domain.models import Prompt, PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_HEADER = re.compile(
    r"^<!--\s*prompt:\s*(?P<name>[\w-]+)\s*·\s*version\s*(?P<version>[\w.-]+)\s*-->\s*\n"
)
_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})


# The mapping codebook (Appendix E) is sent with the prompts of the stages that build the map
# (S1, S2, S3c, S4); its own version is stamped on every draft.
CODEBOOK = "codebook"
CODEBOOK_STAGES = frozenset(
    {
        "S1_extract_interview",
        "S1_extract_document",
        "S1_extract_jd",
        "S2_canonicalise",
        "S3c_worktype",
        "S4_assemble",
    }
)


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> Result[Prompt]:
    """A stage prompt and its version; for the map-building stages, followed by the codebook."""
    match _read_prompt(name, prompts_dir):
        case Err() as err:
            return err
        case Ok(value=prompt):
            pass
    if name not in CODEBOOK_STAGES:
        return Ok(prompt)
    match _read_prompt(CODEBOOK, prompts_dir):
        case Err() as err:
            return err
        case Ok(value=codebook):
            pass
    text = f'{prompt.text}\n\n<codebook version="{codebook.version}">\n{codebook.text}\n</codebook>'
    return Ok(prompt.model_copy(update={"text": text}))


def _read_prompt(name: str, prompts_dir: Path) -> Result[Prompt]:
    path = prompts_dir / f"{name}.md"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return Err(ErrorKind.IO, "A stage prompt is missing from the app.", {"prompt": name})
    header = _HEADER.match(raw)
    if header is None or header.group("name") != name:
        return Err(ErrorKind.IO, "A stage prompt has no version line.", {"prompt": name})
    return Ok(Prompt(name=name, version=header.group("version"), text=raw[header.end() :].strip()))


def instruction_version(path: Path) -> str | None:
    """The version of an instruction file: a prompt's version line, or the `version` field of a
    JSON file such as the question bank; None if it has none or can't be read."""
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            version = json.loads(raw).get("version")
            return str(version) if version else None
    except (OSError, ValueError, AttributeError):
        return None
    header = _HEADER.match(raw)
    return header.group("version") if header else None


def instruction_versions(prompts_dir: Path = PROMPTS_DIR) -> dict[str, str]:
    """Every instruction file's version by name (`S1_extract_interview`, `question_bank`): what a
    run was made with, stamped on its run record so later runs can be compared."""
    return {
        p.stem: version
        for p in sorted(prompts_dir.iterdir())
        if p.suffix in (".md", ".json") and (version := instruction_version(p))
    }


DEFAULT_CONVENTIONS = {"granularity": "standard", "label_style": "standard", "phase_naming": "sme"}


def render_conventions(conventions: dict[str, str] | None) -> str:
    """Eric's codebook tier 2 choices (C7a) as a data line for S2 and S4, or "" when they are the
    defaults the codebook already states (so nothing extra is sent)."""
    chosen = {**DEFAULT_CONVENTIONS, **(conventions or {})}
    if chosen == DEFAULT_CONVENTIONS:
        return ""
    attrs = " ".join(f'{k}="{escape(chosen[k])}"' for k in DEFAULT_CONVENTIONS)
    return f"<conventions {attrs}/>"


def escape(text: str) -> str:
    """Source text can't close a tag or open a new one (G9)."""
    return text.translate(_ESCAPES)


def render_source(source_ref: str, kind: str, segments: Sequence[PromptSegment]) -> str:
    """One source as tagged data: `<source id kind>` holding one `<segment id anchor [speaker]>`
    per passage. Text is escaped; names are expected to be hidden already (G10)."""
    lines = [f'<source id="{escape(source_ref)}" kind="{escape(kind)}">']
    for segment in segments:
        speaker = f' speaker="{escape(segment.speaker_role)}"' if segment.speaker_role else ""
        # Interviews (§3.12.10 steps A and B): the answer block's question and the marker hints.
        question = f' question="{escape(segment.question_id)}"' if segment.question_id else ""
        markers = f' markers="{escape("; ".join(segment.markers))}"' if segment.markers else ""
        lines.append(
            f'<segment id="{escape(segment.ref)}" anchor="{escape(segment.anchor)}"'
            f"{speaker}{question}{markers}>{escape(segment.text)}</segment>"
        )
    lines.append("</source>")
    return "\n".join(lines)


def render_questions(questions: Sequence[BankQuestion]) -> str:
    """The guide questions an interview chunk answers, with what each is designed to produce
    (its targets), so the model knows what each answer is evidence for (§3.12.10 step A)."""
    lines = ["<questions>"]
    for q in questions:
        lines.append(
            f'<question id="{escape(q.id)}" movement="{escape(q.movement)}" '
            f'targets="{escape("; ".join(q.targets))}">{escape(q.wording)}</question>'
        )
    lines.append("</questions>")
    return "\n".join(lines)


def cited_text(segments: Sequence[PromptSegment]) -> str:
    """The text a claim may be checked against: each passage exactly as sent (escaped), with the
    speaker's role in front of transcript turns so G5 can find the role."""
    return "\n".join(
        f"{escape(s.speaker_role)}: {escape(s.text)}" if s.speaker_role else escape(s.text)
        for s in segments
    )
