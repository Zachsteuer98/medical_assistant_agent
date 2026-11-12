"""CLI: build the vector index for a corpus.  uv run python -m app.ingest --corpus merck"""

import argparse
import logging
import time

import pymupdf

from app.config import get_settings
from app.corpora import get_corpus
from app.ingest.chunking import DEFAULT_CHUNK_TOKENS, DEFAULT_OVERLAP_TOKENS, split_text
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
    corpus = get_corpus(corpus_name)
    if not corpus.pdf_path.exists():
        raise FileNotFoundError(f"Corpus PDF not found: {corpus.pdf_path}")
    noise = compile_patterns([*corpus.noise_line_patterns, *extra_patterns.split(",")])
    chunks: list[Chunk] = []
    with pymupdf.open(corpus.pdf_path) as doc:
        for index in range(corpus.first_content_page, doc.page_count):
            text = clean_page_text(doc[index].get_text(), noise)
            chunks.extend(
                Chunk(text=piece, page=index + 1)
                for piece in split_text(text, chunk_tokens, overlap_tokens)
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
        "--collection", default=None, help="Collection name (defaults to the corpus name)"
    )
    args = parser.parse_args()
    settings = get_settings()
    corpus = args.corpus or settings.corpus

    started = time.perf_counter()
    collection = args.collection or corpus
    chunks = load_chunks(
        corpus, settings.watermark_patterns, args.chunk_tokens, args.overlap_tokens
    )
    log.info("chunked corpus=%s collection=%s chunks=%d", corpus, collection, len(chunks))
    total = build_index(settings.chroma_dir, collection, chunks)
    log.info(
        "indexed collection=%s chunks=%d seconds=%.0f",
        collection,
        total,
        time.perf_counter() - started,
    )


if __name__ == "__main__":
    main()
