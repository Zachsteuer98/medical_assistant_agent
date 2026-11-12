import pytest

from app.ingest.chunking import split_text


def words(text: str) -> int:  # deterministic stand-in for a tokenizer
    return len(text.split())


def test_short_text_is_single_chunk():
    assert split_text("one two three", chunk_tokens=10, overlap_tokens=2, count=words) == [
        "one two three"
    ]


def test_long_text_splits_within_budget_with_overlap():
    paragraphs = [f"para{i} " + "word " * 8 for i in range(10)]  # ~9 words each
    text = "\n\n".join(p.strip() for p in paragraphs)
    chunks = split_text(text, chunk_tokens=30, overlap_tokens=10, count=words)

    assert len(chunks) > 1
    assert all(words(c) <= 30 for c in chunks)
    # Overlap: each chunk's first paragraph also appears in the previous chunk.
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.split()[0] in prev
    # Nothing lost.
    assert all(f"para{i}" in " ".join(chunks) for i in range(10))


def test_rejects_overlap_not_smaller_than_chunk():
    with pytest.raises(ValueError):
        split_text("x", chunk_tokens=10, overlap_tokens=10, count=words)
