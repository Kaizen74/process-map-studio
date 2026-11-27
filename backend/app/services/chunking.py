"""Chunking (PRD §3.7): never send a whole engagement in one prompt. No database access.

Transcripts are split into ~10-minute windows by their timestamps (or ~60 speaker turns when there
are none), with a small overlap so an answer that spans a boundary is seen whole at least once.
Documents are split into sections of at most ~15 pages (Word files, which have no pages, into
runs of passages of about the same size). A tidied PDF document whose passages carry the manual's
own sections (DECISIONS 114) is split at those sections instead: whole sections packed together
up to about 30,000 characters of text, a longer section split at a page break.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.models import PromptSegment

WINDOW_MIN = 10
OVERLAP_MIN = 1
TURNS_PER_CHUNK = 60
TURN_OVERLAP = 5
MAX_PAGES = 15
# A Word file has no pages: about 15 pages' worth of passages per chunk.
PASSAGES_PER_CHUNK = 150
# A document read by its sections: the text of one chunk, in characters (about 15 dense pages).
SECTION_CHUNK_CHARS = 30_000


def chunk_transcript(
    segments: Sequence[PromptSegment],
    window_min: int = WINDOW_MIN,
    overlap_min: int = OVERLAP_MIN,
) -> list[list[PromptSegment]]:
    """Time windows of `window_min` minutes starting every `window_min - overlap_min` minutes.

    Passages without a time (headings, notes) go with the passage before them. Without any
    timestamps: runs of `TURNS_PER_CHUNK` turns overlapping by `TURN_OVERLAP`.
    """
    if not segments:
        return []
    if all(s.start_ms is None for s in segments):
        return _by_count(segments, TURNS_PER_CHUNK, TURN_OVERLAP)
    times: list[int] = []
    last = next(s.start_ms for s in segments if s.start_ms is not None)
    for segment in segments:
        last = segment.start_ms if segment.start_ms is not None else last
        times.append(last)
    window, step = window_min * 60_000, max(1, window_min - overlap_min) * 60_000
    chunks: list[list[PromptSegment]] = []
    start = times[0]
    while True:
        chunk = [s for s, t in zip(segments, times, strict=True) if start <= t < start + window]
        if chunk and (not chunks or chunk != chunks[-1]):
            chunks.append(chunk)
        if start + window > times[-1]:
            return chunks
        start += step


def chunk_document(
    segments: Sequence[PromptSegment], max_pages: int = MAX_PAGES
) -> list[list[PromptSegment]]:
    """Consecutive pages, at most `max_pages` per chunk; page-less files by passage count."""
    if not segments:
        return []
    if all(s.page is None for s in segments):
        return _by_count(segments, PASSAGES_PER_CHUNK, 0)
    if any(s.section for s in segments):
        return _by_section(segments, SECTION_CHUNK_CHARS)
    chunks: list[list[PromptSegment]] = []
    current: list[PromptSegment] = []
    first_page = segments[0].page or 1
    for segment in segments:
        page = segment.page if segment.page is not None else first_page
        if current and page - first_page >= max_pages:
            chunks.append(current)
            current, first_page = [], page
        current.append(segment)
    chunks.append(current)
    return chunks


def _by_section(segments: Sequence[PromptSegment], budget: int) -> list[list[PromptSegment]]:
    """Whole sections packed in order up to `budget` characters; a section longer than that is
    split, at a page break where one falls in the second half of the piece, else at a passage."""
    sections: list[list[PromptSegment]] = []
    for segment in segments:
        if sections and sections[-1][-1].section == segment.section:
            sections[-1].append(segment)
        else:
            sections.append([segment])
    pieces: list[list[PromptSegment]] = []
    for section in sections:
        pieces += _split(section, budget)
    chunks: list[list[PromptSegment]] = []
    size = 0
    for piece in pieces:
        length = _chars(piece)
        if chunks and size + length <= budget:
            chunks[-1] += piece
            size += length
        else:
            chunks.append(list(piece))
            size = length
    return chunks


def _chars(segments: Sequence[PromptSegment]) -> int:
    return sum(len(s.text) for s in segments)


def _split(section: list[PromptSegment], budget: int) -> list[list[PromptSegment]]:
    pieces: list[list[PromptSegment]] = []
    rest = section
    while _chars(rest) > budget:
        total, cut = 0, len(rest)
        for index, segment in enumerate(rest):
            total += len(segment.text)
            if total > budget:
                cut = max(1, index)
                break
        breaks = [
            i
            for i in range(cut // 2, cut)
            if i > 0 and rest[i].page is not None and rest[i].page != rest[i - 1].page
        ]
        cut = breaks[-1] if breaks else cut
        pieces.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        pieces.append(rest)
    return pieces


def _by_count(
    segments: Sequence[PromptSegment], size: int, overlap: int
) -> list[list[PromptSegment]]:
    chunks: list[list[PromptSegment]] = []
    start = 0
    while True:
        chunks.append(list(segments[start : start + size]))
        if start + size >= len(segments):
            return chunks
        start += size - overlap
