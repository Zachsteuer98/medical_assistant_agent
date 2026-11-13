"""Registry of supported corpora. Each corpus has its own vector collection (ADR 0001).

A corpus is one or more PDF documents. Page numbers everywhere are 1-based physical PDF page
indexes (what a PDF viewer's page box shows and what `#page=N` links open). For the VA/DoD
guidelines this equals the printed "Page N of M" footer on every page (verified with pymupdf
and pypdf for all ten pinned PDFs).
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw"
CHROMA_ROOT = REPO_ROOT / "data"
MANIFEST_DIR = Path(__file__).resolve().parent / "corpus_manifests"
# Characters that would break the "[Source: <label>, Page: X]" citation marker.
_FORBIDDEN_LABEL_CHARS = frozenset(",[]")
# Inclusive (first, last) 1-based physical page numbers, the same numbering citations use.
PageRange = tuple[int, int]
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


@dataclass(frozen=True)
class CorpusDocument:
    display_name: str  # shown to users in citations, e.g. guideline title + year
    pdf_path: Path
    # 0-based index of the first clinical page; earlier pages are cover/TOC "retrieval traps".
    first_content_page: int
    # Short name the model cites in multi-document corpora; defaults to display_name.
    citation_label: str = ""
    # If set, ingest fails when the PDF's page count differs (wrong or re-published file).
    expected_pages: int | None = None
    # Non-clinical sections (references, search strategies, evidence tables...) that otherwise
    # crowd retrieval results. Sorted, non-overlapping, after first_content_page.
    excluded_pages: tuple[PageRange, ...] = ()

    def __post_init__(self) -> None:
        previous_last = self.first_content_page  # 0-based index == 1-based page before it
        for first, last in self.excluded_pages:
            if not previous_last < first <= last:
                raise ValueError(
                    f"{self.display_name}: excluded page ranges must be ordered, non-overlapping "
                    f"and after the first content page; got {self.excluded_pages}"
                )
            if self.expected_pages is not None and last > self.expected_pages:
                raise ValueError(f"{self.display_name}: excluded page {last} beyond last page")
            previous_last = last

    @property
    def label(self) -> str:
        return self.citation_label or self.display_name

    def is_content_page(self, page: int) -> bool:
        """page is 1-based (as cited)."""
        if page <= self.first_content_page:
            return False
        return not any(first <= page <= last for first, last in self.excluded_pages)


@dataclass(frozen=True)
class CorpusSpec:
    name: str
    display_name: str
    documents: tuple[CorpusDocument, ...]
    # Regexes for lines that are layout noise (running headers etc.), not content.
    noise_line_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.documents:
            raise ValueError(f"Corpus {self.name!r} has no documents")
        names = [d.display_name for d in self.documents]
        labels = [d.label for d in self.documents]
        if len(set(names)) != len(names) or len(set(labels)) != len(labels):
            raise ValueError(f"Corpus {self.name!r} has duplicate document names or labels")
        bad = [label for label in labels if _FORBIDDEN_LABEL_CHARS & set(label)]
        if self.is_multi_document and bad:
            raise ValueError(f"Citation labels must not contain , [ or ]: {bad}")

    @property
    def default_chroma_dir(self) -> Path:
        # Merck keeps its original location so its existing index needs no rebuild.
        return CHROMA_ROOT / ("chroma" if self.name == "merck" else f"chroma_{self.name}")

    def chroma_dir(self, override: Path | None) -> Path:
        return override or self.default_chroma_dir

    @property
    def is_multi_document(self) -> bool:
        return len(self.documents) > 1

    def document_named(self, display_name: str) -> CorpusDocument:
        """Resolve a chunk's stored source name; chunks without one belong to a single-doc corpus.

        Indexes built before multi-document support store no source name, so an empty name maps
        to the only document (this keeps the existing Merck index valid without a rebuild).
        """
        if not display_name and not self.is_multi_document:
            return self.documents[0]
        for doc in self.documents:
            if doc.display_name == display_name:
                return doc
        raise KeyError(f"Document {display_name!r} is not part of corpus {self.name!r}")


def _merck() -> CorpusSpec:
    display_name = "The Merck Manual of Diagnosis & Therapy, 19th ed."
    return CorpusSpec(
        name="merck",
        display_name=display_name,
        documents=(
            CorpusDocument(
                display_name=display_name,
                pdf_path=RAW_DIR / "merck.pdf",
                first_content_page=52,
            ),
        ),
        noise_line_patterns=(r"^The Merck Manual of Diagnosis & Therapy, 19th Edition",),
    )


@dataclass(frozen=True)
class ManifestEntry:
    id: str
    title: str
    year: int
    citation_label: str
    url: str
    sha256: str
    pages: int
    first_content_page: int
    excluded_pages: tuple[PageRange, ...] = ()

    @property
    def display_name(self) -> str:
        return f"{self.title} ({self.year})"


@cache
def load_manifest(corpus_name: str) -> tuple[ManifestEntry, ...]:
    raw = json.loads((MANIFEST_DIR / f"{corpus_name}.json").read_text(encoding="utf-8"))
    base = raw["base_url"].rstrip("/")
    return tuple(
        ManifestEntry(
            id=d["id"],
            title=d["title"],
            year=int(d["year"]),
            citation_label=d["citation_label"],
            url=base + d["url_path"],
            sha256=d["sha256"],
            pages=int(d["pages"]),
            first_content_page=int(d["first_content_page"]),
            excluded_pages=tuple((int(a), int(b)) for a, b in d.get("excluded_pages", ())),
        )
        for d in raw["documents"]
    )


def manifest_pdf_path(corpus_name: str, entry: ManifestEntry) -> Path:
    return RAW_DIR / corpus_name / f"{entry.id}.pdf"


def _public() -> CorpusSpec:
    return CorpusSpec(
        name="public",
        display_name="VA/DoD Clinical Practice Guidelines",
        documents=tuple(
            CorpusDocument(
                display_name=e.display_name,
                pdf_path=manifest_pdf_path("public", e),
                first_content_page=e.first_content_page,
                citation_label=e.citation_label,
                expected_pages=e.pages,
                excluded_pages=e.excluded_pages,
            )
            for e in load_manifest("public")
        ),
        noise_line_patterns=(
            # Running header. Headers never end with a period; reference-list entries citing
            # other VA/DoD guidelines do, so they survive.
            r"^(?i:VA/DoD) Clinical Practice Guideline (?:for|on) [^.]+$",
            rf"^(?:{_MONTHS}) \d{{4}}$",  # header publication date
            r"^Page \d+ of \d+$",
        ),
    )


CORPORA: dict[str, CorpusSpec] = {"merck": _merck(), "public": _public()}


def get_corpus(name: str) -> CorpusSpec:
    try:
        return CORPORA[name]
    except KeyError as exc:
        raise ValueError(f"Unknown corpus {name!r}; expected one of {sorted(CORPORA)}") from exc
