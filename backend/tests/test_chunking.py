import re

import pytest

from app.corpora import VA_DOD_RECOMMENDATION_HEADING, VA_DOD_RECOMMENDATION_ROW, get_corpus
from app.ingest.chunking import split_text, split_text_structured


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


# --- structure-aware splitting (public corpus: recommendation headings and table rows) ----

HEADING = re.compile(VA_DOD_RECOMMENDATION_HEADING, re.MULTILINE)
ROW = re.compile(VA_DOD_RECOMMENDATION_ROW, re.MULTILINE)


def structured(text: str, chunk_tokens: int = 30, overlap_tokens: int = 10) -> list[str]:
    return split_text_structured(text, HEADING, ROW, chunk_tokens, overlap_tokens, count=words)


def test_recommendation_heading_starts_a_fresh_chunk_without_overlap():
    """Regression (P08): Rec 8's statement was glued to the tail of Rec 7's discussion."""
    text = (
        "Rec7 discussion tail: patients prefer few side effects. Strong for recommendation.\n"
        "Recommendation \n"
        "8. In patients with moderate to severe symptom burden, we recommend LABA/LAMA over \n"
        "monotherapy.\n(Strong for | Reviewed, New-added)\nDiscussion\nEvidence supports it."
    )
    chunks = structured(text, chunk_tokens=200)

    assert len(chunks) == 2
    assert chunks[1].startswith("Recommendation \n8. In patients")
    assert "Rec7" not in chunks[1]
    # The heading's own numbered line is not a second boundary.
    assert "8. In patients" not in chunks[0]


def _row(n: int, drug: str) -> str:
    return f"{n}. For patients with low back pain, we suggest against {drug}.\nWeak against\n"


def test_table_rows_are_packed_whole_and_chunks_break_only_between_rows():
    drugs = ["opioids", "acetaminophen", "benzodiazepines", "corticosteroids", "antibodies"]
    text = "Topic # Recommendation Strength\n" + "".join(
        _row(n, d) for n, d in enumerate(drugs, 24)
    )
    chunks = structured(text, chunk_tokens=30)

    assert len(chunks) < len(drugs)  # rows share chunks
    assert all(words(c) <= 30 for c in chunks)
    for chunk in chunks[1:]:
        assert re.match(r"\d+\. For patients", chunk)  # every later chunk opens on a row
    for n, drug in enumerate(drugs, 24):  # no row is cut: number and drug stay together
        assert any(f"{n}. For patients" in c and drug in c for c in chunks)


def test_bare_number_table_rows_are_recognised():
    rows = [
        f"{n} \nWe suggest {d} for the prevention of migraine. \nWeak for \n"
        for n, d in ((10, "propranolol"), (11, "valproate"), (12, "memantine"))
    ]
    chunks = structured("".join(rows), chunk_tokens=12, overlap_tokens=2)
    assert [c.split()[0] for c in chunks] == ["10", "11", "12"]


def test_numbered_lists_that_are_not_recommendations_do_not_split():
    text = (
        "Domains considered:\n1. Confidence in the quality of the evidence\n"
        "2. Balance of desirable and undesirable outcomes\n3. Patient values and preferences"
    )
    assert structured(text, chunk_tokens=200) == [text]


def test_long_recommendation_section_is_still_split_at_the_token_cap():
    text = "Recommendation \n9. In patients with COPD we recommend triple therapy. " + (
        "Evidence sentence with several words here. " * 30
    )
    chunks = structured(text, chunk_tokens=30, overlap_tokens=10)

    assert len(chunks) > 3
    assert all(words(c) <= 30 for c in chunks)
    assert chunks[0].startswith("Recommendation \n9. In patients")


def test_without_patterns_structured_split_is_exactly_split_text():
    """Merck: no structure patterns, so chunking (and its existing index) is unchanged."""
    text = (
        "Intro text about sepsis.\n\nRecommendation \n8. We recommend fluids early.\n"
        + "Body sentence with words. " * 40
    )
    for size, overlap in ((30, 10), (200, 40)):
        assert split_text_structured(text, None, None, size, overlap, count=words) == split_text(
            text, size, overlap, count=words
        )


def test_only_the_public_corpus_uses_structure_aware_chunking():
    merck, public = get_corpus("merck"), get_corpus("public")
    assert merck.section_boundary_pattern is None and merck.item_boundary_pattern is None
    assert public.section_boundary_pattern == VA_DOD_RECOMMENDATION_HEADING
    assert public.item_boundary_pattern == VA_DOD_RECOMMENDATION_ROW
