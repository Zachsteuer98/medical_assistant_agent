"""Chroma-backed vector store: index building (ingest) and MMR retrieval (serving)."""

import logging
import shutil
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.rag.mmr import mmr_select

ADD_BATCH_SIZE = 256
CHROMA_DB_FILE = "chroma.sqlite3"
log = logging.getLogger("store")


class IndexNotReadyError(RuntimeError):
    """The vector collection for the configured corpus has not been built."""


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int  # 1-based PDF page
    # Display name of the source document. Empty for indexes built before multi-document
    # corpora existed; the corpus resolves that to its only document.
    source: str = ""


def chunk_metadata(chunk: Chunk) -> dict[str, str | int]:
    return {"page": chunk.page, "source": chunk.source}


def chunk_from_record(text: str, metadata: Mapping[str, object]) -> Chunk:
    return Chunk(text=text, page=int(metadata["page"]), source=str(metadata.get("source", "")))


class Retriever(Protocol):
    def retrieve(self, question: str, k: int) -> list[Chunk]: ...

    def count(self) -> int: ...


def _client(chroma_dir: Path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=str(chroma_dir), settings=ChromaSettings(anonymized_telemetry=False)
    )


def _segment_ids(chroma_dir: Path, collection_id: str) -> list[str]:
    """Segment ids of one collection, read from Chroma's catalog (schema of chromadb 1.5.x)."""
    db = sqlite3.connect(f"file:{chroma_dir / CHROMA_DB_FILE}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT id FROM segments WHERE collection = ?", (collection_id,))
        return [str(row[0]) for row in rows]
    finally:
        db.close()


def _delete_collection(client: chromadb.ClientAPI, chroma_dir: Path, name: str) -> None:
    """Delete a collection and its on-disk vector segment directories.

    Chroma's delete_collection leaves the HNSW directory behind, so every re-ingest leaked one
    (~10 MB for the public corpus). Only directories of *this* collection, looked up before the
    delete, are removed, so other collections sharing the store are never touched.
    """
    collection_id = str(client.get_collection(name).id)
    segment_dirs = [chroma_dir / sid for sid in _segment_ids(chroma_dir, collection_id)]
    client.delete_collection(name)
    for directory in segment_dirs:
        if directory.is_dir():
            shutil.rmtree(directory)
            log.info("removed stale segment dir=%s", directory.name)


def build_index(
    chroma_dir: Path,
    collection: str,
    chunks: Sequence[Chunk],
    embedding_function: Any = None,
) -> int:
    """(Re)create the collection from scratch so re-ingesting is idempotent."""
    client = _client(chroma_dir)
    if collection in [c.name for c in client.list_collections()]:
        _delete_collection(client, chroma_dir, collection)
    col = client.create_collection(
        collection,
        # Default: all-MiniLM-L6-v2 (ONNX), 384-d. Tests inject a tiny deterministic one.
        embedding_function=embedding_function or DefaultEmbeddingFunction(),
        configuration={"hnsw": {"space": "cosine"}},
    )
    for start in range(0, len(chunks), ADD_BATCH_SIZE):
        batch = chunks[start : start + ADD_BATCH_SIZE]
        col.add(
            ids=[f"{collection}-{start + i}" for i in range(len(batch))],
            documents=[c.text for c in batch],
            metadatas=[chunk_metadata(c) for c in batch],
        )
    return col.count()


class ChromaRetriever:
    def __init__(self, chroma_dir: Path, collection: str, fetch_k: int, mmr_lambda: float):
        self._embed = DefaultEmbeddingFunction()
        try:
            self._col = _client(chroma_dir).get_collection(
                collection, embedding_function=self._embed
            )
        except Exception as exc:  # chroma raises different types across versions
            raise IndexNotReadyError(
                f"No index for corpus {collection!r} in {chroma_dir}. "
                f"Run: uv run python -m app.ingest --corpus {collection}"
            ) from exc
        self._fetch_k = fetch_k
        self._mmr_lambda = mmr_lambda

    def count(self) -> int:
        return self._col.count()

    def retrieve(self, question: str, k: int) -> list[Chunk]:
        result = self._col.query(
            query_texts=[question],
            n_results=self._fetch_k,
            include=["documents", "metadatas", "embeddings"],
        )
        docs, metas = result["documents"][0], result["metadatas"][0]
        vectors = np.asarray(result["embeddings"][0], dtype=np.float64)

        # Drop exact duplicates (overlap at page boundaries produced them in the notebook).
        seen: set[str] = set()
        unique = [i for i, d in enumerate(docs) if not (d.strip() in seen or seen.add(d.strip()))]
        if not unique:
            return []

        query_vec = np.asarray(self._embed([question])[0], dtype=np.float64)
        picked = mmr_select(query_vec, vectors[unique], k, self._mmr_lambda)
        return [chunk_from_record(docs[unique[i]], metas[unique[i]]) for i in picked]
