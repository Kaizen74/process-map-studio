"""Document parsing (PRD §3.2, §3.7 S0): files → anchored segments. No database access.

Verified against python-docx 1.2.0 (`Document.iter_inner_content()` yields Paragraph and Table in
body order; `Paragraph.style.name`, `.text`; `Table.rows[].cells[].text`), pdfplumber 0.11.10
(`pdfplumber.open(path).pages[].extract_text()`) and pypdf 6.19.0 (`PdfReader(path).pages[].images`
→ ImageFile with `.name`, `.data`, `.image` (Pillow)).

Transcripts (phase P2): plain text with `Speaker: text` or `[mm:ss] Speaker: text` turns, WebVTT
cues (with `<v Speaker>` voice tags or a `Speaker:` prefix) and SubRip (.srt) cues. Word and PDF
transcripts are read as documents first, then `detect_speakers` turns their lines into speaker
turns. Lines without a speaker continue the turn before them (PDF line wrapping, page breaks).
"""

from __future__ import annotations

import io
import re
from itertools import pairwise
from pathlib import Path

import pdfplumber
import pypdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.domain.models import ExtractedImage, ParsedDocument, ParsedSegment
from app.domain.result import Err, ErrorKind, Ok, Result

OCR_THRESHOLD_CHARS = 50  # PRD §3.7 S0: pages with fewer characters are treated as scans
MIN_IMAGE_SIDE_PX = 48  # smaller images (bullets, logos, rules) are not worth suggesting
_CLAUSE = re.compile(r"^(§\s?\d+(?:\.\d+)*|\d+(?:\.\d+)+)\s")
_WHITESPACE = re.compile(r"[ \t\xa0]+")  # spaces, tabs, non-breaking spaces

# A speaker turn: optional [h:mm:ss] or [mm:ss], a short label, a colon, then the words spoken.
# Labels are 1-5 words of letters, digits, dots, hyphens and apostrophes ("Priya Nair", "SME 2").
_TURN = re.compile(
    r"^\[?(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})?\]?\s*"
    r"(?:(?P<label>[^\W\d_][\w.'\u2019-]*(?: [\w.'\u2019-]+){0,4})\s*:\s+)?(?P<text>.*)$"
)
_CUE_TIME = re.compile(
    r"(?P<start>(?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*(?P<end>(?:\d+:)?\d{2}:\d{2}[.,]\d{3})"
)
_VOICE = re.compile(r"<v(?:\.[\w.-]+)?\s+(?P<label>[^>]+)>")
_TAG = re.compile(r"</?[^>]+>")


def _tidy(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _is_heading(paragraph: Paragraph) -> bool:
    name = paragraph.style.name if paragraph.style is not None else ""
    return name.startswith("Heading") or name == "Title"


def parse_docx(path: Path) -> Result[ParsedDocument]:
    """Paragraphs and table rows become segments; the latest heading is each one's section."""
    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises several unrelated types for bad files
        return Err(
            ErrorKind.IO, "The Word document could not be opened.", {"reason": type(exc).__name__}
        )
    segments: list[ParsedSegment] = []
    section = ""
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = _tidy(block.text)
            if not text:
                continue
            if _is_heading(block):
                section = text
            segments.append(ParsedSegment(seq=len(segments) + 1, text=text, section=section))
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [_tidy(cell.text) for cell in row.cells]
                text = " | ".join(c for c in cells if c)
                if text:
                    segments.append(
                        ParsedSegment(seq=len(segments) + 1, text=text, section=section)
                    )
    return Ok(ParsedDocument(segments=segments))


def parse_pdf_text(path: Path) -> Result[ParsedDocument]:
    """The text layer, one segment per non-empty paragraph, anchored by page number.

    Pages with fewer than 50 characters are listed in `ocr_pages` (PRD §3.7 S0; OCR from P3).
    """
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # pdfminer raises many types for damaged files
        return Err(ErrorKind.IO, "The PDF could not be read.", {"reason": type(exc).__name__})
    segments: list[ParsedSegment] = []
    ocr_pages: list[int] = []
    for number, text in enumerate(pages, start=1):
        if len(text.strip()) < OCR_THRESHOLD_CHARS:
            ocr_pages.append(number)
            continue
        for line in text.splitlines():
            clean = _tidy(line)
            if clean:
                segments.append(ParsedSegment(seq=len(segments) + 1, text=clean, page=number))
    return Ok(ParsedDocument(segments=segments, ocr_pages=ocr_pages, page_count=len(pages)))


def extract_pdf_images(path: Path) -> Result[list[ExtractedImage]]:
    """Embedded images with their page numbers, as suggestions for Eric to keep or discard."""
    try:
        reader = pypdf.PdfReader(str(path))
        found: list[ExtractedImage] = []
        for number, page in enumerate(reader.pages, start=1):
            for image in page.images:
                picture = image.image
                if picture is None:
                    continue
                width, height = picture.size
                if min(width, height) < MIN_IMAGE_SIDE_PX:
                    continue
                extension = Path(image.name).suffix.lstrip(".").lower() or "png"
                found.append(
                    ExtractedImage(
                        page=number,
                        name=image.name,
                        extension=extension,
                        data=image.data,
                        width=width,
                        height=height,
                    )
                )
    except Exception as exc:  # pypdf and Pillow raise many types for damaged images
        return Err(
            ErrorKind.IO, "Images in the PDF could not be read.", {"reason": type(exc).__name__}
        )
    return Ok(found)


def split_pdf_page(path: Path, page: int) -> Result[bytes]:
    """One page of a PDF as a PDF of its own (for reading a scanned page, PRD §3.7 S0).

    Verified in pypdf 6.19.0: `PdfWriter().add_page(reader.pages[i])`, `write(stream)`; the output
    is byte-identical between runs.
    """
    try:
        reader = pypdf.PdfReader(str(path))
        if not 1 <= page <= len(reader.pages):
            return Err(ErrorKind.NOT_FOUND, "That page isn't in the PDF.", {"page": page})
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[page - 1])
        out = io.BytesIO()
        writer.write(out)
    except Exception as exc:  # pypdf raises many types for damaged files
        return Err(ErrorKind.IO, "The PDF page could not be read.", {"reason": type(exc).__name__})
    return Ok(out.getvalue())


def segment_anchor(
    *, fmt: str, seq: int, page: int | None, section: str, text: str, start_ms: int | None = None
) -> str:
    """The short reference shown next to a passage: "§3.2", "p. 3", "06:40" or "¶ 4"."""
    if start_ms is not None:
        seconds = start_ms // 1000
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    clause = _CLAUSE.match(text)
    if clause:
        number = clause.group(1).replace(" ", "")
        return number if number.startswith("§") else f"§{number}"
    if page is not None and fmt == "pdf":
        return f"p. {page}"
    return f"¶ {seq}"


# --- Transcripts (phase P2) ---------------------------------------------------------------------


def _read_text(path: Path) -> Result[str]:
    """Text files as UTF-8 (with or without a byte-order mark), else Windows-1252."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return Err(ErrorKind.IO, "The file could not be opened.", {"reason": type(exc).__name__})
    try:
        return Ok(data.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return Ok(data.decode("cp1252", errors="replace"))


def _stamp_ms(stamp: str) -> int:
    """ "06:40" → 400000; "1:02:03" → 3723000; "00:06:40.500" or "00:06:40,500" → 400500."""
    whole, _, fraction = stamp.replace(",", ".").partition(".")
    seconds = 0
    for part in whole.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds * 1000 + (int(fraction.ljust(3, "0")[:3]) if fraction else 0)


def _split_turn(line: str) -> tuple[int | None, str, str]:
    """(start_ms, speaker label, spoken text) for one line; label "" when it names no speaker."""
    match = _TURN.match(line)
    if match is None:  # the pattern always matches; kept for the type checker
        return None, "", line
    stamp, label, text = match.group("ts"), match.group("label") or "", match.group("text")
    if stamp is None and not line.lstrip().startswith(label or "\0"):
        label = ""
    if stamp is None and not label:
        return None, "", line
    return (_stamp_ms(stamp) if stamp else None), _tidy(label), _tidy(text)


def detect_speakers(segments: list[ParsedSegment]) -> list[ParsedSegment]:
    """Turn document lines into speaker turns.

    A line starting with `Speaker:` or `[mm:ss] Speaker:` starts a new turn; any other line
    continues the turn before it (so wrapped lines and page breaks don't split what was said).
    Word headings stay separate passages without a speaker.
    Each turn keeps the page and section of its first line; `end_ms` is the next turn's start.
    """
    turns: list[ParsedSegment] = []
    for segment in segments:
        if segment.section and segment.text == segment.section:  # a heading is never a turn
            turns.append(segment.model_copy(update={"seq": len(turns) + 1}))
            continue
        start_ms, label, text = _split_turn(segment.text)
        starts_turn = bool(label) or start_ms is not None
        if not starts_turn and turns:
            previous = turns[-1]
            previous.text = f"{previous.text} {_tidy(segment.text)}".strip()
            continue
        if not label and turns and start_ms is not None:
            label = turns[-1].speaker_label  # "[mm:ss] more words" keeps the last speaker
        turns.append(
            ParsedSegment(
                seq=len(turns) + 1,
                text=text if starts_turn else _tidy(segment.text),
                page=segment.page,
                section=segment.section,
                speaker_label=label,
                start_ms=start_ms,
            )
        )
    for current, following in pairwise(turns):
        if current.start_ms is not None and following.start_ms is not None:
            current.end_ms = following.start_ms
    return [turn for turn in turns if turn.text]


def parse_transcript_text(path: Path) -> Result[ParsedDocument]:
    """Plain-text transcripts: `Speaker: text` or `[mm:ss] Speaker: text`, one turn per line."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    lines = [ParsedSegment(seq=n, text=line) for n, line in enumerate(text.splitlines(), 1)]
    return Ok(ParsedDocument(segments=detect_speakers([s for s in lines if s.text.strip()])))


def parse_text_document(path: Path) -> Result[ParsedDocument]:
    """Plain-text documents (not transcripts): one passage per paragraph (blank-line separated)."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    segments: list[ParsedSegment] = []
    for paragraph in paragraphs:
        clean = _tidy(" ".join(paragraph.split("\n")))
        if clean:
            segments.append(ParsedSegment(seq=len(segments) + 1, text=clean))
    return Ok(ParsedDocument(segments=segments))


def _cues(text: str) -> list[tuple[int, int, list[str]]]:
    """(start_ms, end_ms, payload lines) for each timed cue in a VTT or SRT file."""
    cues: list[tuple[int, int, list[str]]] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = [line for line in block.split("\n") if line.strip()]
        for index, line in enumerate(lines):
            timing = _CUE_TIME.search(line)
            if timing:
                payload = lines[index + 1 :]
                cues.append((_stamp_ms(timing["start"]), _stamp_ms(timing["end"]), payload))
                break
    return cues


def _cue_segments(cues: list[tuple[int, int, list[str]]]) -> list[ParsedSegment]:
    """One segment per cue; a cue with no speaker continues the previous speaker."""
    segments: list[ParsedSegment] = []
    speaker = ""
    for start_ms, end_ms, payload in cues:
        raw = " ".join(payload)
        voice = _VOICE.search(raw)
        label = _tidy(voice["label"]) if voice else ""
        text = _tidy(_TAG.sub("", raw))
        if not voice:
            _, prefixed, rest = _split_turn(text)
            if prefixed:
                label, text = prefixed, rest
        speaker = label or speaker
        if text:
            segments.append(
                ParsedSegment(
                    seq=len(segments) + 1,
                    text=text,
                    speaker_label=speaker,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )
    return segments


def parse_vtt(path: Path) -> Result[ParsedDocument]:
    """WebVTT captions: cue times, speakers from `<v Name>` voice tags or a `Name:` prefix."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    if not text.lstrip().startswith("WEBVTT"):
        return Err(ErrorKind.VALIDATION, "This .vtt file doesn't start with WEBVTT.")
    return Ok(ParsedDocument(segments=_cue_segments(_cues(text))))


def parse_srt(path: Path) -> Result[ParsedDocument]:
    """SubRip captions: numbered cues with `00:06:40,000 --> …` times and `Name:` prefixes."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    return Ok(ParsedDocument(segments=_cue_segments(_cues(text))))


# Words that mark a speaker label as a role or a generic tag rather than a person's name.
_NOT_NAMES = frozenset(
    """interviewer interviewee speaker moderator facilitator host participant respondent sme
    unknown unidentified q a question answer note narrator voice audience all both other team
    lead manager controller supervisor agent captain officer engineer operator planner
    coordinator analyst director head chief staff member crew pilot ramp load control airline
    customer client vendor driver clerk assistant admin administrator representative rep expert
    specialist technician inspector auditor dispatcher system""".split()  # noqa: SIM905
)
_NAME_WORD = re.compile(r"^[A-Z][a-zà-öø-ÿ'\u2019.-]*(?:-[A-Z][a-zà-öø-ÿ'\u2019.-]*)?$")


def looks_like_name(label: str, known_roles: frozenset[str] = frozenset()) -> bool:
    """True when a speaker label looks like a person's name ("Priya Nair"), not a role.

    1-4 capitalised words, no digits, none of them a role or generic word, and not a known role
    name or alias (compared ignoring case).
    """
    text = _tidy(label)
    words = text.split(" ")
    if not text or len(words) > 4 or text.casefold() in known_roles:
        return False
    return all(
        _NAME_WORD.match(word) and word.strip(".").casefold() not in _NOT_NAMES for word in words
    )
