"""Token-aware recursive text splitter (same strategy as the notebook's
RecursiveCharacterTextSplitter.from_tiktoken_encoder, without the LangChain dependency)."""

import re
from collections.abc import Callable
from functools import lru_cache

import tiktoken

TokenCounter = Callable[[str], int]
SEPARATORS = ("\n\n", "\n", ". ", " ")
DEFAULT_CHUNK_TOKENS = 200  # fits MiniLM's 256-wordpiece window; see ADR 0003
DEFAULT_OVERLAP_TOKENS = 40


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


def _atomize(text: str, max_tokens: int, count: TokenCounter, seps: tuple[str, ...]) -> list[str]:
    """Recursively split until every piece fits, preferring coarse separators."""
    if count(text) <= max_tokens or not seps:
        return [text]
    sep, finer = seps[0], seps[1:]
    parts = text.split(sep)
    pieces: list[str] = []
    for i, part in enumerate(parts):
        piece = part + (sep if i < len(parts) - 1 else "")
        if piece:
            pieces.extend(_atomize(piece, max_tokens, count, finer))
    return pieces


def split_text(
    text: str,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    count: TokenCounter = count_tokens,
) -> list[str]:
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be smaller than chunk_tokens")
    units = [(u, count(u)) for u in _atomize(text, chunk_tokens, count, SEPARATORS)]
    chunks: list[str] = []
    window: list[tuple[str, int]] = []
    window_tokens = 0
    for unit, tokens in units:
        if window and window_tokens + tokens > chunk_tokens:
            chunks.append("".join(u for u, _ in window).strip())
            # Keep a tail of the window as overlap so ideas spanning a boundary survive.
            while window and window_tokens > overlap_tokens:
                window_tokens -= window.pop(0)[1]
        window.append((unit, tokens))
        window_tokens += tokens
    if window:
        chunks.append("".join(u for u, _ in window).strip())
    return [c for c in chunks if c]


def split_at_boundaries(text: str, boundary: re.Pattern[str], after: int = 0) -> list[str]:
    """Cut text into segments; each boundary match starting after `after` opens a segment."""
    starts = sorted({0, *(m.start() for m in boundary.finditer(text) if m.start() > after)})
    return [text[a:b] for a, b in zip(starts, [*starts[1:], len(text)], strict=True)]


def _pack(
    items: list[str], chunk_tokens: int, overlap_tokens: int, count: TokenCounter
) -> list[str]:
    """Greedily pack whole items up to chunk_tokens; an oversized item is split on its own."""
    chunks: list[str] = []
    buffer, buffer_tokens = "", 0
    for item in items:
        tokens = count(item)
        if tokens > chunk_tokens or (buffer and buffer_tokens + tokens > chunk_tokens):
            chunks.append(buffer)
            buffer, buffer_tokens = "", 0
        if tokens > chunk_tokens:
            chunks.extend(split_text(item, chunk_tokens, overlap_tokens, count))
        else:
            buffer, buffer_tokens = buffer + item, buffer_tokens + tokens
    chunks.append(buffer)
    return [c.strip() for c in chunks if c.strip()]


def split_text_structured(
    text: str,
    section: re.Pattern[str] | None,
    item: re.Pattern[str] | None,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    count: TokenCounter = count_tokens,
) -> list[str]:
    """split_text that respects document structure.

    - A `section` match (e.g. a recommendation heading in a discussion) always starts a new
      chunk, and no overlap is carried into it: overlap is what glued the tail of one
      recommendation's discussion onto the next recommendation statement.
    - Inside a section, chunk breaks fall only at `item` matches (e.g. recommendation-table
      rows): short items are packed whole up to chunk_tokens, so a row is never cut mid-way
      and a table still fits in a few chunks.
    - Anything longer than chunk_tokens is split as before, with overlap.
    With neither pattern this is exactly split_text.
    """
    if section is None and item is None:
        return split_text(text, chunk_tokens, overlap_tokens, count)
    chunks: list[str] = []
    for part in split_at_boundaries(text, section) if section else [text]:
        heading = section.match(part) if section else None
        # The heading's own numbered line is not a second boundary.
        items = split_at_boundaries(part, item, heading.end() if heading else 0) if item else [part]
        chunks.extend(_pack(items, chunk_tokens, overlap_tokens, count))
    return chunks
