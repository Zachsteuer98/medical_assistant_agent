"""CLI: build the vector index for a corpus.  uv run python -m app.ingest --corpus merck

For the public corpus, fetch the PDFs first: uv run python -m app.download --corpus public
"""

import argparse
import logging
import re
import time

import pymupdf

from app.config import get_settings
from app.corpora import CorpusDocument, CorpusSpec, get_corpus
from app.ingest.chunking import (
    DEFAULT_CHUNK_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    split_text_structured,
)
from app.ingest.cleaning import clean_page_text, compile_patterns
from app.rag.store import Chunk, build_index

MIN_CHUNK_CHARS = 50  # drop near-empty fragments (figure labels, stray headers)
log = logging.getLogger("ingest")


def load_chunks(
    corpus_name: str,
    extra_patterns: str,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    return load_corpus_chunks(get_corpus(corpus_name), extra_patterns, chunk_tokens, overlap_tokens)


def load_corpus_chunks(
    corpus: CorpusSpec,
    extra_patterns: str = "",
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    missing = [str(d.pdf_path) for d in corpus.documents if not d.pdf_path.exists()]
    if missing:
        raise FileNotFoundError(f"Corpus PDF(s) not found: {', '.join(missing)}")
    noise = compile_patterns([*corpus.noise_line_patterns, *extra_patterns.split(",")])
    structure = (
        _multiline(corpus.section_boundary_pattern),
        _multiline(corpus.item_boundary_pattern),
    )
    chunks: list[Chunk] = []
    for document in corpus.documents:
        doc_chunks = _document_chunks(document, noise, structure, chunk_tokens, overlap_tokens)
        log.info("chunked document=%r chunks=%d", document.display_name, len(doc_chunks))
        chunks.extend(doc_chunks)
    return chunks


def _multiline(pattern: str | None) -> re.Pattern[str] | None:
    return re.compile(pattern, re.MULTILINE) if pattern else None


def _document_chunks(
    document: CorpusDocument,
    noise: tuple[re.Pattern[str], ...],
    structure: tuple[re.Pattern[str] | None, re.Pattern[str] | None],
    chunk_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    with pymupdf.open(document.pdf_path) as doc:
        if document.expected_pages is not None and doc.page_count != document.expected_pages:
            raise ValueError(
                f"{document.pdf_path} has {doc.page_count} pages, expected "
                f"{document.expected_pages}; re-download it or update the manifest"
            )
        for index in range(document.first_content_page, doc.page_count):
            if not document.is_content_page(index + 1):
                continue
            text = clean_page_text(doc[index].get_text(), noise)
            chunks.extend(
                # Page = 1-based physical PDF page, what a PDF viewer shows (see app.corpora).
                Chunk(text=piece, page=index + 1, source=document.display_name)
                for piece in split_text_structured(text, *structure, chunk_tokens, overlap_tokens)
                if len(piece) >= MIN_CHUNK_CHARS
            )
    return chunks


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=None, help="Corpus name (defaults to CORPUS env)")
    parser.add_argument("--chunk-tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    parser.add_argument("--overlap-tokens", type=int, default=DEFAULT_OVERLAP_TOKENS)
    parser.add_argument(
        "--collection", default=None, help="Collection name (defaults to the corpus's collection)"
    )
    args = parser.parse_args()
    settings = get_settings()
    corpus = args.corpus or settings.corpus

    started = time.perf_counter()
    collection = args.collection or get_corpus(corpus).default_collection
    chunks = load_chunks(
        corpus, settings.watermark_patterns, args.chunk_tokens, args.overlap_tokens
    )
    log.info("chunked corpus=%s collection=%s chunks=%d", corpus, collection, len(chunks))
    chroma_dir = get_corpus(corpus).chroma_dir(settings.chroma_dir)
    total = build_index(chroma_dir, collection, chunks)
    log.info(
        "indexed collection=%s dir=%s chunks=%d seconds=%.0f",
        collection,
        chroma_dir,
        total,
        time.perf_counter() - started,
    )


if __name__ == "__main__":
    main()
