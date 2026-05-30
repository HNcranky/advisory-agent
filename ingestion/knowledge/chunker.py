import re
from dataclasses import dataclass

from ingestion.config.settings import CHUNK_SIZE, CHUNK_OVERLAP

# Blank-line block boundary (also matches the line before a "[Trang N]" marker
# because markers are emitted preceded by a blank line in pdf_pages.py).
_BLOCK_SEP = re.compile(r"\n[ \t]*\n")
# Sentence-ish cut points for hard-splitting an oversized single block.
_SENTENCE_END = re.compile(r"[.!?。]\s|\n")


@dataclass
class Chunk:
    chunk_text: str
    span_start: int
    span_end: int


def _block_break_offsets(text: str) -> list[int]:
    """Sorted candidate cut offsets at block boundaries, plus end-of-text."""
    offs = {len(text)}
    for m in _BLOCK_SEP.finditer(text):
        if m.start() > 0:
            offs.add(m.start())
    return sorted(offs)


def _largest_le(values: list[int], limit: int) -> int | None:
    best = None
    for v in values:
        if v <= limit:
            best = v
        else:
            break
    return best


def _sentence_cut(text: str, start: int, hard_limit: int) -> int:
    """Last sentence boundary in (start, hard_limit], else hard_limit."""
    window = text[start:hard_limit]
    last = None
    for m in _SENTENCE_END.finditer(window):
        last = m.end()
    if last is not None and last > 0:
        return start + last
    return hard_limit


def split_into_chunks(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    n = len(text)
    if n == 0:
        return []

    breaks = _block_break_offsets(text)
    chunks: list[Chunk] = []
    start = 0
    while start < n:
        hard_limit = start + size
        if hard_limit >= n:
            end = n
        else:
            candidate = _largest_le(breaks, hard_limit)
            if candidate is not None and candidate > start:
                end = candidate
            else:
                end = _sentence_cut(text, start, hard_limit)

        body = text[start:end].strip()
        if body:
            chunks.append(Chunk(chunk_text=body, span_start=start, span_end=end))

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks
