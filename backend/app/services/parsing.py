"""Document parsing (PRD §3.2, §3.7 S0): files → anchored segments. No database access.

Verified against python-docx 1.2.0 (`Document.iter_inner_content()` yields Paragraph and Table in
body order; `Paragraph.style.name`, `.text`; `Table.rows[].cells[].text`), pdfplumber 0.11.10
(`pdfplumber.open(path).pages[].extract_text()`) and pypdf 6.19.0 (`PdfReader(path).pages[].images`
→ ImageFile with `.name`, `.data`, `.image` (Pillow)).

Spreadsheets and emails (P10b R11): openpyxl 3.1.5 (`load_workbook(path, read_only=True,
data_only=True)`, `Workbook.worksheets`, `Worksheet.iter_rows(values_only=True)`, `.title`,
`Workbook.close()`; with defusedxml 0.7.1 installed openpyxl parses the XML through it) and the
standard library `csv` and `email` (`BytesParser(policy=policy.default)`, `EmailMessage.get_body`,
`iter_attachments`, `get_content`; `email.utils.getaddresses`, `parsedate_to_datetime`).

Transcripts (phase P2): plain text with `Speaker: text` or `[mm:ss] Speaker: text` turns, WebVTT
cues (with `<v Speaker>` voice tags or a `Speaker:` prefix) and SubRip (.srt) cues. Word and PDF
transcripts are read as documents first, then `detect_speakers` turns their lines into speaker
turns. Lines without a speaker continue the turn before them (PDF line wrapping, page breaks).
"""

from __future__ import annotations

import csv
import io
import re
import warnings
from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime, time
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path
from typing import Any

import pdfplumber
import pypdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook

from app.domain.models import ExtractedImage, ParsedDocument, ParsedSegment
from app.domain.result import Err, ErrorKind, Ok, Result

OCR_THRESHOLD_CHARS = 50  # PRD §3.7 S0: pages with fewer characters are treated as scans
MIN_IMAGE_SIDE_PX = 48  # smaller images (bullets, logos, rules) are not worth suggesting
LOGO_MIN_PAGES = 3  # the same picture on this many pages is a logo or header, never suggested
# Process-flow diagram pages (2026-10-28): text boxes, in PDF points.
BOX_MIN_WIDTH, BOX_MIN_HEIGHT = 80, 20
BOX_MIN_WORDS = 3  # a box holding fewer words is a decoration, not a stage
BOX_TOUCH_PT = 2  # boxes this close are table cells
DIAGRAM_MIN_BOXES = 3
LABEL_MAX_GAP_PT = 120  # a label this far to the left of a box belongs to it
LABEL_LINE_GAP_PT = 6  # the lines of one label are this close
COLUMN_TOLERANCE_PT = 20  # boxes whose left edges are this close form one column
_CLAUSE = re.compile(r"^(§\s?\d+(?:\.\d+)*|\d+(?:\.\d+)+)\s")
_WHITESPACE = re.compile(r"[ \t\xa0]+")  # spaces, tabs, non-breaking spaces

# A speaker turn: optional [h:mm:ss] or [mm:ss], a short label, a colon, then the words spoken.
# Labels are 1-5 words of letters, digits, dots, hyphens and apostrophes ("Priya Nair", "SME 2").
_TURN = re.compile(
    r"^\[?(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})?\]?\s*"
    r"(?:(?P<label>[^\W\d_][\w.'\u2019-]*(?: [\w.'\u2019-]+){0,4})\s*:\s+)?(?P<text>.*)$"
)
# An Otter.ai text export: a line holding only the speaker and the time ("Speaker 1  0:06",
# "Alex Tan  1:02:03"), separated by two or more spaces or a tab; the words follow on the lines
# below. The footer "Transcribed by https://otter.ai" is not part of the conversation.
_OTTER_HEAD = re.compile(
    r"^(?P<label>[^\W\d_][\w.'\u2019-]*(?: [\w.'\u2019-]+){0,4})(?: {2,}|\t)\s*"
    r"(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\s*$"
)
_OTTER_FOOTER = re.compile(r"^\s*Transcribed by https?://(?:www\.)?otter\.ai\S*\s*$", re.IGNORECASE)
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


Box = tuple[float, float, float, float]  # x0, top, x1, bottom in PDF points


def _boxes(page: Any) -> list[Box]:
    """The text boxes of a diagram: rectangles at least 80 x 20 points that touch no other one
    (cells of a table touch their neighbours) and hold no other box (a frame)."""
    found: list[Box] = []
    for r in page.rects:
        box = (float(r["x0"]), float(r["top"]), float(r["x1"]), float(r["bottom"]))
        if box[2] - box[0] < BOX_MIN_WIDTH or box[3] - box[1] < BOX_MIN_HEIGHT:
            continue
        if not any(all(abs(a - b) < 1 for a, b in zip(box, other, strict=True)) for other in found):
            found.append(box)

    def touches(a: Box, b: Box) -> bool:
        gap_x = max(a[0], b[0]) - min(a[2], b[2])
        gap_y = max(a[1], b[1]) - min(a[3], b[3])
        return gap_x <= BOX_TOUCH_PT and gap_y <= BOX_TOUCH_PT

    def holds(a: Box, b: Box) -> bool:
        return a != b and a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]

    return [b for b in found if not any(touches(b, o) or holds(b, o) for o in found if o != b)]


def _inside(word: dict[str, Any], box: Box) -> bool:
    return bool(
        word["x0"] >= box[0] - 1 and word["x1"] <= box[2] + 1
        and word["top"] >= box[1] - 1 and word["bottom"] <= box[3] + 1
    )  # fmt: skip


def _lines(words: list[dict[str, Any]]) -> list[tuple[float, str]]:
    """Words → lines (top, text): words whose tops are within 3 points, left to right."""
    lines: list[tuple[float, list[dict[str, Any]]]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0] - word["top"]) <= 3:
            lines[-1][1].append(word)
        else:
            lines.append((word["top"], [word]))
    return [(top, _tidy(" ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]))))
            for top, ws in lines]  # fmt: skip


def _blocks(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Words → blocks of stacked lines that overlap sideways (a label of one or more lines)."""
    blocks: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        for block in blocks:
            left, right = min(w["x0"] for w in block), max(w["x1"] for w in block)
            bottom = max(w["bottom"] for w in block)
            beside = word["x0"] <= right + 4 and word["x1"] >= left - 4
            same_line = any(abs(w["top"] - word["top"]) <= 3 for w in block)
            if (same_line and word["x0"] <= right + 8) or (
                beside and 0 <= word["top"] - bottom <= LABEL_LINE_GAP_PT
            ):
                block.append(word)
                break
        else:
            blocks.append([word])
    return blocks


def _area_text(page: Any, box: Box) -> str:
    """The text inside an area, its lines joined (read on its own, letter-spaced words stay
    whole)."""
    area = page.within_bbox((box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1))
    return " ".join(_tidy(line) for line in (area.extract_text() or "").splitlines())


def _diagram_page(page: Any) -> list[str] | None:
    """A process-flow diagram page read box by box (Eric's cargo manual, 2026-10-28), or None for
    any other page. Each box becomes one passage, its lines joined, with the team label printed
    beside it (to its left) in front: "RAMP TEAM: 2. LOAD THE AIRCRAFT • …". Boxes are read column
    by column, top to bottom; text outside the boxes stays line by line (headings first)."""
    boxes = _boxes(page)
    words = [w for w in page.extract_words(extra_attrs=["upright"]) if w["upright"]]
    texts = {b: [w for w in words if _inside(w, b)] for b in boxes}
    boxes = [b for b in boxes if len(texts[b]) >= BOX_MIN_WORDS]
    if len(boxes) < DIAGRAM_MIN_BOXES:
        return None
    outside = [w for w in words if not any(_inside(w, b) for b in boxes)]
    labels: dict[Box, list[str]] = {b: [] for b in boxes}
    rest: list[dict[str, Any]] = []
    for block in _blocks(outside):
        x1 = max(w["x1"] for w in block)
        top, bottom = min(w["top"] for w in block), max(w["bottom"] for w in block)
        near = [
            b
            for b in boxes
            if 0 <= b[0] - x1 + 2 <= LABEL_MAX_GAP_PT + 2 and top < b[3] and bottom > b[1]
        ]
        if near:
            box = min(near, key=lambda b: b[0] - x1)
            area = (min(w["x0"] for w in block), top, x1, bottom)
            labels[box].append(_area_text(page, area))
        else:
            rest += block
    first_top = min(b[1] for b in boxes)
    lines = _lines(rest)
    columns: list[list[Box]] = []
    for box in sorted(boxes, key=lambda b: (b[0], b[1])):
        if columns and abs(columns[-1][0][0] - box[0]) <= COLUMN_TOLERANCE_PT:
            columns[-1].append(box)
        else:
            columns.append([box])
    passages = []
    for column in columns:
        for box in sorted(column, key=lambda b: b[1]):
            body = _area_text(page, box)
            label = " / ".join(labels[box])
            passages.append(f"{label}: {body}" if label else body)
    return (
        [text for top, text in lines if top < first_top]
        + passages
        + [text for top, text in lines if top >= first_top]
    )


def parse_pdf_text(path: Path) -> Result[ParsedDocument]:
    """The text layer, one segment per non-empty line, anchored by page number; a process-flow
    diagram page one segment per box, with its team label (`_diagram_page`).

    Pages with fewer than 50 characters are listed in `ocr_pages` (PRD §3.7 S0; OCR from P3).
    """
    try:
        with pdfplumber.open(path) as pdf:
            pages = [(page.extract_text() or "", _diagram_page(page)) for page in pdf.pages]
    except Exception as exc:  # pdfminer raises many types for damaged files
        return Err(ErrorKind.IO, "The PDF could not be read.", {"reason": type(exc).__name__})
    segments: list[ParsedSegment] = []
    ocr_pages: list[int] = []
    for number, (text, diagram) in enumerate(pages, start=1):
        if len(text.strip()) < OCR_THRESHOLD_CHARS:
            ocr_pages.append(number)
            continue
        for line in diagram if diagram is not None else text.splitlines():
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
    # The same picture on many pages is a logo or a header (2026-10-28: one on all 39 pages of
    # Eric's manual), never a picture of the work.
    pages: dict[bytes, set[int]] = {}
    for extracted in found:
        pages.setdefault(extracted.data, set()).add(extracted.page)
    return Ok([i for i in found if len(pages[i.data]) < LOGO_MIN_PAGES])


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
    if fmt == "xlsx" and page is not None:  # the sheet and the row's cell in column A (R11)
        return f"{sheet_ref(section)}!A{page}"
    if fmt == "csv" and page is not None:
        return f"row {page}"
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


def _from_otter(lines: list[str]) -> list[str]:
    """Otter.ai blocks ("Speaker 1  0:06" then the words) as `[0:06] Speaker 1: words` lines;
    other lines are kept as they are."""
    out: list[str] = []
    empty: set[int] = set()  # speaker lines with no words below them (dropped)
    in_turn = False  # inside an Otter block: every line belongs to its speaker
    for line in lines:
        if _OTTER_FOOTER.match(line):
            continue
        head = _OTTER_HEAD.match(line)
        if head:
            empty.add(len(out))
            out.append(f"[{head.group('ts')}] {head.group('label')}:")
            in_turn = True
        elif in_turn and line.strip():
            empty.discard(len(out) - 1)
            out[-1] = f"{out[-1]} {line.strip()}"
        elif not in_turn:
            out.append(line)
    return [line for n, line in enumerate(out) if n not in empty]


def parse_transcript_text(path: Path) -> Result[ParsedDocument]:
    """Plain-text transcripts: `Speaker: text` or `[mm:ss] Speaker: text`, one turn per line, or
    an Otter.ai export (speaker and time on their own line, the words below)."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    raw = _from_otter(text.splitlines())
    lines = [ParsedSegment(seq=n, text=line) for n, line in enumerate(raw, 1)]
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
    specialist technician inspector auditor dispatcher system desk ops operations office support
    service services helpdesk group department dept unit centre center mailbox inbox
    noreply""".split()  # noqa: SIM905
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


# --- Spreadsheets and emails (P10b R11) ----------------------------------------------------------

MAX_SHEET_ROWS = 5000  # filled rows in one spreadsheet; more is a system export, not an artefact
TOO_MANY_ROWS = (
    "This spreadsheet has more than 5,000 filled rows. If it is a system export, import it under "
    "System records; otherwise save only the rows that matter and upload again."
)
NO_CELLS = "The spreadsheet has no filled cells."
NOT_AN_EMAIL = "This .eml file doesn't look like an email."
_PLAIN_SHEET = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def sheet_ref(name: str) -> str:
    """A sheet name as Excel writes it in a reference: `Load plan` → `'Load plan'`."""
    if _PLAIN_SHEET.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


def _cell_text(value: object) -> str:
    """A cell's value as text: 12.0 → "12", dates as 2026-03-02 (with " 09:14" when timed)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".10g")
    if isinstance(value, datetime):
        if value.time() == time(0, 0):
            return value.date().isoformat()
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return _tidy(str(value))


def _is_header(cells: Sequence[object]) -> bool:
    filled = [c for c in cells if c not in (None, "")]
    return len(filled) >= 2 and all(isinstance(c, str) for c in filled)


def _row_segments(
    rows: Iterable[tuple[int, Sequence[object]]], section: str, start: int
) -> Iterator[ParsedSegment]:
    """One passage per filled row; below the header row each reads `Header: value | …`."""
    headers: list[str] | None = None
    seq = start
    for number, cells in rows:
        texts = [_cell_text(c) for c in cells]
        if not any(texts):
            continue
        if headers is None and _is_header(cells):
            headers = texts
            text = " | ".join(t for t in texts if t)
        elif headers is not None:
            parts = []
            for column, value in enumerate(texts):
                if not value:
                    continue
                header = headers[column] if column < len(headers) else ""
                parts.append(f"{header}: {value}" if header else value)
            text = " | ".join(parts)
        else:
            text = " | ".join(t for t in texts if t)
        seq += 1
        yield ParsedSegment(seq=seq, text=text, page=number, section=section)


def _limited(segments: list[ParsedSegment]) -> Result[ParsedDocument]:
    if not segments:
        return Err(ErrorKind.VALIDATION, NO_CELLS)
    return Ok(ParsedDocument(segments=segments))


def parse_xlsx(path: Path) -> Result[ParsedDocument]:
    """A working spreadsheet: one passage per filled row, sheet by sheet, anchored `Sheet!A5`."""
    segments: list[ParsedSegment] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # openpyxl warns about features it doesn't read
            book = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet in book.worksheets:
                    rows = enumerate(sheet.iter_rows(values_only=True), start=1)
                    for segment in _row_segments(rows, sheet.title, len(segments)):
                        segments.append(segment)
                        if len(segments) > MAX_SHEET_ROWS:
                            return Err(ErrorKind.VALIDATION, TOO_MANY_ROWS)
            finally:
                book.close()
    except Exception as exc:  # openpyxl and zipfile raise many types for damaged files
        return Err(
            ErrorKind.IO, "The spreadsheet could not be opened.", {"reason": type(exc).__name__}
        )
    return _limited(segments)


def parse_csv(path: Path) -> Result[ParsedDocument]:
    """A CSV working spreadsheet: as one sheet, each passage anchored `row 5` (its record)."""
    match _read_text(path):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(
            text[:4096], delimiters=",;\t|"
        )
    except csv.Error:
        dialect = csv.excel
    segments: list[ParsedSegment] = []
    try:
        rows = enumerate(csv.reader(io.StringIO(text), dialect), start=1)
        for segment in _row_segments(rows, "", 0):
            segments.append(segment)
            if len(segments) > MAX_SHEET_ROWS:
                return Err(ErrorKind.VALIDATION, TOO_MANY_ROWS)
    except csv.Error as exc:
        return Err(ErrorKind.IO, "The CSV file could not be read.", {"reason": type(exc).__name__})
    return _limited(segments)


class _HtmlText(HTMLParser):
    """The text of an HTML email body, one line per block; scripts and styles left out."""

    BLOCKS = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
                        "blockquote", "table", "ul", "ol", "hr"})  # fmt: skip
    SKIP = frozenset({"script", "style", "head", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


def _html_text(html: str) -> str:
    parser = _HtmlText()
    parser.feed(html)
    parser.close()
    lines = [_tidy(line) for line in "".join(parser.parts).split("\n")]
    # Paragraph breaks where the HTML had empty blocks; single block ends are line ends.
    return "\n".join(lines)


_ADDRESS_HEADERS = ("From", "Sender", "Reply-To", "To", "Cc", "Bcc")
_WROTE = re.compile(r"^On\b(?P<who>.+)\bwrote:$", re.IGNORECASE)
_ORIGINAL = re.compile(
    r"^-{2,}\s*(?:Original Message|Forwarded message)\s*-{2,}$|^_{10,}$", re.IGNORECASE
)
_QUOTED_FIELD = re.compile(r"^(?P<field>From|Sent|Date|To|Cc|Subject)\s*:\s*(?P<value>.*)$", re.I)
_EMAIL_SECTION = "Email"
_EARLIER = "Earlier in the thread"
MAX_ATTACHED_DEPTH = 5


def _people(values: Iterable[str]) -> list[tuple[str, str]]:
    """(display name, address) for every person a header names."""
    return [(_tidy(name), addr.strip()) for name, addr in getaddresses(list(values))]


_LOOSE_PERSON = re.compile(r'^"?(?P<name>[^"<>]*?)"?\s*(?:<(?P<addr>[^<>\s]+)>)?$')


def _loose_people(value: str) -> list[tuple[str, str]]:
    """People in a quoted header line as mail programs print it ("Priya Nair", "Nair, Priya
    <p@x.com>", "A; B"): split on semicolons, and on commas only between several addresses."""
    parts = [
        part
        for chunk in value.split(";")
        for part in (chunk.split(",") if chunk.count("@") > 1 else [chunk])
    ]
    out: list[tuple[str, str]] = []
    for part in (p.strip() for p in parts):
        if not part:
            continue
        if "@" in part and " " not in part and "<" not in part:
            out.append(("", part))
        elif match := _LOOSE_PERSON.match(part):
            out.append((_tidy(match["name"]), (match["addr"] or "").strip()))
    return out


def _who(people: Sequence[tuple[str, str]]) -> str:
    """The first person's display name, else their address; "" when neither is usable."""
    if not people:
        return ""
    name, addr = people[0]
    return name or (addr if "@" in addr else "")


def _names_of(people: Iterable[tuple[str, str]]) -> list[str]:
    """Display names and addresses to hide; "Tan, Wei Ming" also as "Wei Ming Tan"."""
    out: list[str] = []
    for name, addr in people:
        if name and "@" not in name:
            out.append(name)
            last, comma, first = name.partition(",")
            if comma and first.strip() and last.strip():
                out.append(f"{first.strip()} {last.strip()}")
        if "@" in addr:
            out.append(addr)
    return out


def _shown(people: Iterable[tuple[str, str]]) -> str:
    return ", ".join(name or addr for name, addr in people if name or addr)


def _sent(message: EmailMessage) -> str:
    raw = message.get("Date")
    if not raw:
        return ""
    try:
        moment = parsedate_to_datetime(str(raw))
    except (TypeError, ValueError, IndexError):
        return _tidy(str(raw))
    offset = moment.strftime("%z")
    zone = f" {offset[:3]}:{offset[3:]}" if offset else ""
    return moment.strftime("%Y-%m-%d %H:%M") + zone


def _body(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if not isinstance(part, EmailMessage):
        return ""
    try:
        content = part.get_content()
    except (LookupError, ValueError, AssertionError):  # an unknown charset or a broken part
        payload = part.get_payload(decode=True)
        content = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else ""
    text = str(content)
    return _html_text(text) if part.get_content_type() == "text/html" else text


def _quote_start(lines: list[str], index: int) -> bool:
    """An Outlook reply block: a `From:` line followed within four lines by Sent, Date or To."""
    if not lines[index].lower().startswith("from:"):
        return False
    return any(
        re.match(r"^(Sent|Date|To|Subject)\s*:", line, re.IGNORECASE)
        for line in lines[index + 1 : index + 5]
    )


def _body_segments(
    text: str, section: str, sender: str, start: int
) -> tuple[list[ParsedSegment], list[str]]:
    """Paragraph passages of one email body, and the names its quote lines show (to hide)."""
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [re.sub(r"^(?:\s*>)+\s?", "", line).rstrip() for line in raw_lines]
    quoted_marks = [bool(re.match(r"^\s*>", line)) for line in raw_lines]
    segments: list[ParsedSegment] = []
    names: list[str] = []
    paragraph: list[str] = []
    current, speaker, signature, quoted = section, sender, False, False

    def flush() -> None:
        words = _tidy(" ".join(paragraph))
        paragraph.clear()
        if words:
            segments.append(
                ParsedSegment(
                    seq=start + len(segments) + 1,
                    text=words,
                    section=current,
                    speaker_label=speaker,
                )
            )

    def enter_quote(who: str) -> None:
        nonlocal current, speaker, signature, quoted
        flush()
        current, speaker, signature, quoted = _EARLIER, who, False, True

    for index, line in enumerate(lines):
        clean = line.strip()
        wrote = _WROTE.match(clean)
        if _ORIGINAL.match(clean):
            enter_quote("")
        elif wrote:
            # "On <date>, Name <addr> wrote:": the person follows the last comma. Without a
            # comma the name can't be told from the date, so the quote is left unattributed.
            people = _loose_people(wrote.group("who").rsplit(",", 1)[-1])
            people = [(n if not re.search(r"\d", n) else "", a) for n, a in people]
            names += _names_of(people)
            enter_quote(_who(people))
        elif _quote_start(lines, index) or (quoted and _QUOTED_FIELD.match(clean)):
            field = _QUOTED_FIELD.match(clean)
            assert field is not None  # _quote_start implies a From: line
            name = field.group("field").lower()
            if name in {"from", "to", "cc"}:
                people = _loose_people(field.group("value"))
                names += _names_of(people)
                if name == "from":
                    enter_quote(_who(people))
        elif quoted_marks[index] and not quoted:
            enter_quote("")
            paragraph.append(clean)
        elif not quoted and raw_lines[index].rstrip("\n") in ("-- ", "--"):
            flush()
            signature = True
        elif signature:
            continue
        elif not clean:
            flush()
        else:
            paragraph.append(clean)
    flush()
    return segments, names


def _email_segments(
    message: EmailMessage, number: int, start: int, depth: int = 0
) -> tuple[list[ParsedSegment], list[str]]:
    """One email and the emails attached to it: a header passage, then its paragraphs."""
    section = f"{_EMAIL_SECTION} {number}"
    by_header = {h: _people(str(v) for v in message.get_all(h, [])) for h in _ADDRESS_HEADERS}
    names = [n for people in by_header.values() for n in _names_of(people)]
    sender = _who(by_header["From"] or by_header["Sender"])
    fields = [
        ("From", _shown(by_header["From"])),
        ("To", _shown(by_header["To"])),
        ("Cc", _shown(by_header["Cc"])),
        ("Sent", _sent(message)),
        ("Subject", _tidy(str(message.get("Subject") or ""))),
    ]
    header = " · ".join(f"{label}: {value}" for label, value in fields if value)
    segments = [ParsedSegment(seq=start + 1, text=header, section=section)] if header else []
    body, quoted_names = _body_segments(_body(message), section, sender, start + len(segments))
    segments += body
    names += quoted_names
    if depth < MAX_ATTACHED_DEPTH:
        for part in message.iter_attachments():
            if part.get_content_type() != "message/rfc822":
                continue
            inner = part.get_content()
            if isinstance(inner, EmailMessage):
                more, more_names = _email_segments(
                    inner, number + 1, start + len(segments), depth + 1
                )
                number += 1
                segments += more
                names += more_names
    return segments, names


def parse_eml(path: Path) -> Result[ParsedDocument]:
    """An email thread saved as .eml: headers and paragraphs, senders as speakers; every name
    and address in the headers is returned to be hidden (G10)."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return Err(ErrorKind.IO, "The file could not be opened.", {"reason": type(exc).__name__})
    message = BytesParser(policy=policy.default).parsebytes(data)
    if not isinstance(message, EmailMessage) or not any(
        message.get(h) for h in ("From", "Subject", "Date")
    ):
        return Err(ErrorKind.VALIDATION, NOT_AN_EMAIL)
    try:
        segments, names = _email_segments(message, 1, 0)
    except (LookupError, ValueError, TypeError) as exc:  # malformed parts or headers
        return Err(ErrorKind.IO, "The email could not be read.", {"reason": type(exc).__name__})
    return Ok(ParsedDocument(segments=segments, hidden_names=list(dict.fromkeys(names))))
