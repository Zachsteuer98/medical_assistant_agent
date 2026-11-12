"""Token-aware recursive text splitter (same strategy as the notebook's
RecursiveCharacterTextSplitter.from_tiktoken_encoder, without the LangChain dependency)."""

from collections.abc import Callable
from functools import lru_cache

import tiktoken

TokenCounter = Callable[[str], int]
SEPARATORS = ("\n\n", "\n", ". ", " ")
DEFAULT_CHUNK_TOKENS = 1000
DEFAULT_OVERLAP_TOKENS = 200


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
