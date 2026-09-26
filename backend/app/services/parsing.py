"""Document parsing (PRD §3.2, §3.7 S0): files → anchored segments. No database access.

Verified against python-docx 1.2.0 (`Document.iter_inner_content()` yields Paragraph and Table in
body order; `Paragraph.style.name`, `.text`; `Table.rows[].cells[].text`), pdfplumber 0.11.10
(`pdfplumber.open(path).pages[].extract_text()`) and pypdf 6.19.0 (`PdfReader(path).pages[].images`
→ ImageFile with `.name`, `.data`, `.image` (Pillow)). Transcript formats arrive in phase P2.
"""

from __future__ import annotations

import re
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
