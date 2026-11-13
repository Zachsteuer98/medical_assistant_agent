from pathlib import Path

import pytest

from app.corpora import CorpusDocument, CorpusSpec
from app.ingest.__main__ import load_corpus_chunks
from app.rag.store import Chunk, chunk_from_record, chunk_metadata
from tests.pdfs import make_pdf

BODY = "Clinical content sentence number {n} about treatment and monitoring. " * 3
HEADER = "Running Header of the Guideline"


def page(n: int) -> str:
    return f"{HEADER}\n{BODY.format(n=n)}"


def corpus(*docs: CorpusDocument) -> CorpusSpec:
    return CorpusSpec(
        name="t", display_name="T", documents=docs, noise_line_patterns=(rf"^{HEADER}$",)
    )


def test_multi_document_ingest_tags_each_chunk_with_its_document(tmp_path: Path):
    a = make_pdf(tmp_path / "a.pdf", ["COVER A", "TOC A", page(3), page(4)])
    b = make_pdf(tmp_path / "b.pdf", ["COVER B", page(2)])
    spec = corpus(
        CorpusDocument("Guideline A (2023)", a, first_content_page=2, citation_label="A"),
        CorpusDocument("Guideline B (2025)", b, first_content_page=1, citation_label="B"),
    )

    chunks = load_corpus_chunks(spec)

    assert [(c.source, c.page) for c in chunks] == [
        ("Guideline A (2023)", 3),
        ("Guideline A (2023)", 4),
        ("Guideline B (2025)", 2),
    ]
    assert all(HEADER not in c.text and "COVER" not in c.text for c in chunks)
    assert "number 4" in chunks[1].text  # page N = 1-based physical page index


def test_single_document_ingest_keeps_merck_page_convention(tmp_path: Path):
    """Regression: single-doc corpora skip front matter and number pages index + 1."""
    pdf = make_pdf(tmp_path / "m.pdf", ["front", "front", "front", page(4), page(5)])
    spec = corpus(CorpusDocument("Manual", pdf, first_content_page=3))
    chunks = load_corpus_chunks(spec)
    assert [c.page for c in chunks] == [4, 5]
    assert {c.source for c in chunks} == {"Manual"}


def test_ingest_fails_when_page_count_differs_from_manifest(tmp_path: Path):
    pdf = make_pdf(tmp_path / "a.pdf", [page(1), page(2)])
    spec = corpus(CorpusDocument("A", pdf, 0, expected_pages=165))
    with pytest.raises(ValueError, match="has 2 pages, expected 165"):
        load_corpus_chunks(spec)


def test_ingest_lists_every_missing_pdf(tmp_path: Path):
    spec = corpus(
        CorpusDocument("A", tmp_path / "a.pdf", 0, citation_label="A"),
        CorpusDocument("B", tmp_path / "b.pdf", 0, citation_label="B"),
    )
    with pytest.raises(FileNotFoundError, match=r"a\.pdf.*b\.pdf"):
        load_corpus_chunks(spec)


def test_chunk_metadata_round_trips_source_and_page():
    chunk = Chunk("text", 12, "Guideline A (2023)")
    assert chunk_from_record("text", chunk_metadata(chunk)) == chunk


def test_legacy_metadata_without_source_still_loads():
    """Regression: the existing Merck index stores only {"page": N}."""
    assert chunk_from_record("text", {"page": 175}) == Chunk("text", 175, "")


def test_excluded_page_ranges_are_skipped_inclusive_1_based(tmp_path: Path):
    pdf = make_pdf(tmp_path / "a.pdf", ["cover", page(2), page(3), page(4), page(5), page(6)])
    spec = corpus(CorpusDocument("A", pdf, 1, excluded_pages=((3, 4), (6, 6))))
    assert [c.page for c in load_corpus_chunks(spec)] == [2, 5]


def test_exclusions_apply_per_document(tmp_path: Path):
    a = make_pdf(tmp_path / "a.pdf", [page(1), page(2)])
    b = make_pdf(tmp_path / "b.pdf", [page(1), page(2)])
    spec = corpus(
        CorpusDocument("A", a, 0, citation_label="A", excluded_pages=((2, 2),)),
        CorpusDocument("B", b, 0, citation_label="B"),
    )
    assert [(c.source, c.page) for c in load_corpus_chunks(spec)] == [("A", 1), ("B", 1), ("B", 2)]
