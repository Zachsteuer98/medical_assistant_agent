from pathlib import Path

import pytest

from app.config import REPO_ROOT
from app.corpora import CorpusDocument, CorpusSpec, get_corpus, load_manifest
from app.ingest.cleaning import clean_page_text, compile_patterns
from tests.fakes import MULTI_CORPUS, TEST_CORPUS


def test_merck_spec_is_unchanged_single_document():
    """Regression: the existing Merck collection/index must stay valid without a rebuild."""
    merck = get_corpus("merck")
    assert merck.name == "merck"
    assert merck.display_name == "The Merck Manual of Diagnosis & Therapy, 19th ed."
    assert not merck.is_multi_document
    (doc,) = merck.documents
    assert doc.pdf_path == REPO_ROOT / "data" / "raw" / "merck.pdf"
    assert doc.first_content_page == 52
    assert doc.display_name == merck.display_name
    assert doc.expected_pages is None
    assert merck.noise_line_patterns == (r"^The Merck Manual of Diagnosis & Therapy, 19th Edition",)


def test_public_corpus_has_ten_pinned_guidelines():
    public = get_corpus("public")
    assert public.is_multi_document
    assert len(public.documents) == 10
    for doc in public.documents:
        assert doc.pdf_path.parent == REPO_ROOT / "data" / "raw" / "public"
        assert doc.display_name.startswith("VA/DoD Clinical Practice Guideline")
        assert doc.display_name.endswith(")")  # "(<year>)"
        assert doc.expected_pages and 0 < doc.first_content_page < doc.expected_pages


def test_public_manifest_pins_https_urls_and_digests():
    entries = load_manifest("public")
    assert len({e.id for e in entries}) == len(entries)
    for e in entries:
        assert e.url.startswith("https://www.healthquality.va.gov/HEALTHQUALITY/guidelines/")
        assert e.url.endswith(".pdf")
        assert len(e.sha256) == 64 and int(e.sha256, 16) >= 0


def test_empty_source_resolves_to_only_document_of_single_doc_corpus():
    assert TEST_CORPUS.document_named("") is TEST_CORPUS.documents[0]


def test_unknown_or_empty_source_in_multi_doc_corpus_fails_fast():
    with pytest.raises(KeyError):
        MULTI_CORPUS.document_named("")
    with pytest.raises(KeyError):
        MULTI_CORPUS.document_named("Some other guideline")


def test_multi_doc_corpus_rejects_labels_that_break_citation_markers():
    docs = (
        CorpusDocument("A", Path("a.pdf"), 0, citation_label="Diabetes, 2023"),
        CorpusDocument("B", Path("b.pdf"), 0),
    )
    with pytest.raises(ValueError, match="must not contain"):
        CorpusSpec(name="x", display_name="X", documents=docs)


def test_corpus_rejects_duplicate_labels_and_empty_document_list():
    dup = (
        CorpusDocument("A", Path("a.pdf"), 0, citation_label="Same"),
        CorpusDocument("B", Path("b.pdf"), 0, citation_label="Same"),
    )
    with pytest.raises(ValueError, match="duplicate"):
        CorpusSpec(name="x", display_name="X", documents=dup)
    with pytest.raises(ValueError, match="no documents"):
        CorpusSpec(name="x", display_name="X", documents=())


PUBLIC_PAGE = """VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus
May 2023
Page 61 of 165
Metformin is recommended as first-line therapy.
12. VA/DoD Clinical Practice Guideline for the Management of Major Depressive Disorder. 2016."""


def test_public_noise_patterns_strip_running_header_but_keep_references():
    noise = compile_patterns(get_corpus("public").noise_line_patterns)
    cleaned = clean_page_text(PUBLIC_PAGE, noise)
    assert cleaned.splitlines() == [
        "Metformin is recommended as first-line therapy.",
        "12. VA/DoD Clinical Practice Guideline for the Management of Major Depressive Disorder. "
        "2016.",
    ]


def test_public_header_pattern_matches_all_title_variants():
    noise = compile_patterns(get_corpus("public").noise_line_patterns)
    for header in (
        "VA/DOD Clinical Practice Guideline for the Primary Care Management of Asthma",
        "VA/DOD Clinical Practice Guideline on Lipid Management for Cardiovascular Disease Risk "
        "Reduction",
        "VA/DOD Clinical Practice Guideline for Diagnosis and Treatment of Hypertension in "
        "Primary Care",
        " Page 182 of 182 ",
        "September 2026",
    ):
        assert clean_page_text(header, noise) == "", header


def test_merck_keeps_its_store_and_public_gets_a_separate_one():
    """Regression: an interrupted public ingest once wrote into the Merck Chroma DB. The public
    demo must be deployable without shipping a database file that holds licensed data."""
    assert get_corpus("merck").chroma_dir(None) == REPO_ROOT / "data" / "chroma"
    assert get_corpus("public").chroma_dir(None) == REPO_ROOT / "data" / "chroma_public"
    assert get_corpus("public").chroma_dir(Path("/data/chroma")) == Path("/data/chroma")


def test_merck_has_no_excluded_pages():
    """Regression: page exclusions are opt-in; Merck's chunking must not change."""
    (doc,) = get_corpus("merck").documents
    assert doc.excluded_pages == ()
    assert not doc.is_content_page(52) and doc.is_content_page(53)
    assert doc.is_content_page(3000)


def test_is_content_page_respects_front_matter_and_inclusive_ranges():
    doc = CorpusDocument("A", Path("a.pdf"), 4, excluded_pages=((60, 98), (112, 123)))
    assert [doc.is_content_page(p) for p in (4, 5, 59, 60, 98, 99, 111, 112, 123)] == [
        False, True, True, False, False, True, True, False, False,
    ]


@pytest.mark.parametrize(
    "ranges",
    [((10, 5),), ((5, 10), (8, 12)), ((20, 30), (5, 10)), ((3, 10),), ((90, 101),)],
    ids=["reversed", "overlapping", "unsorted", "inside-front-matter", "past-last-page"],
)
def test_invalid_excluded_ranges_are_rejected(ranges):
    with pytest.raises(ValueError):
        CorpusDocument("A", Path("a.pdf"), 4, expected_pages=100, excluded_pages=ranges)


def test_public_manifest_excludes_references_and_keeps_recommendations():
    docs = {d.citation_label: d for d in get_corpus("public").documents}
    htn = docs["Hypertension CPG 2026"]
    # Verified against the PDF: recommendations p.26-57 kept; Appendix A-F (methodology,
    # evidence table, categorization, participants, focus group, search strategy) p.60-98,
    # abbreviations and references p.112-123 excluded; dosing table p.102 kept.
    assert htn.excluded_pages == ((60, 98), (112, 123))
    assert all(htn.is_content_page(p) for p in (26, 36, 57, 99, 102, 107))
    for doc in docs.values():  # every guideline ends with excluded references
        assert doc.excluded_pages and doc.excluded_pages[-1][1] == doc.expected_pages
