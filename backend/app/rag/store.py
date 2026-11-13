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

from app.rag.lexical import BM25Index, ranks, reciprocal_rank_fusion
from app.rag.mmr import mmr_select
from app.rag.routing import RoutingConfig, route_documents

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


class _ChunkTable:
    """Every chunk of a collection in memory, for exact hybrid scoring inside routed documents.

    Only built for hybrid retrieval (multi-document corpora: ~4k chunks, ~6 MB of vectors).
    """

    def __init__(self, col: Any):
        got = col.get(include=["documents", "metadatas", "embeddings"])
        self.texts: list[str] = got["documents"]
        self.metas: list[Mapping[str, object]] = got["metadatas"]
        vectors = np.asarray(got["embeddings"], dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        self.vectors = vectors / np.where(norms == 0, 1, norms)
        self.sources = np.array([str(m.get("source", "")) for m in self.metas])
        self.bm25 = BM25Index(self.texts)

    def indices(self, documents: list[str] | None) -> np.ndarray:
        if documents is None:
            return np.arange(len(self.texts))
        return np.flatnonzero(np.isin(self.sources, documents))


class ChromaRetriever:
    def __init__(
        self,
        chroma_dir: Path,
        collection: str,
        fetch_k: int,
        mmr_lambda: float,
        routing: RoutingConfig | None = None,
        hybrid: bool = False,
    ):
        if hybrid and routing is None:
            raise ValueError("hybrid retrieval requires document routing")
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
        # None: plain MMR over the whole collection (single-document corpora, routing off).
        self._routing = routing
        self._table = _ChunkTable(self._col) if hybrid else None

    def count(self) -> int:
        return self._col.count()

    def retrieve(self, question: str, k: int) -> list[Chunk]:
        if self._routing is not None:
            return self._retrieve_routed(question, k, self._routing)
        result = self._col.query(
            query_texts=[question],
            n_results=self._fetch_k,
            include=["documents", "metadatas", "embeddings"],
        )
        query_vec = np.asarray(self._embed([question])[0], dtype=np.float64)
        return self._select(result, query_vec, k)

    def _retrieve_routed(self, question: str, k: int, routing: RoutingConfig) -> list[Chunk]:
        # Embed once: the query embedding dominates retrieval latency on CPU (~0.3 s).
        query_vec = np.asarray(self._embed([question])[0], dtype=np.float64)
        documents = self._route(query_vec, routing)
        if self._table is not None:
            return self._retrieve_hybrid(question, query_vec, documents, k, self._table)
        filters = {"where": _source_filter(documents)} if documents else {}
        result = self._col.query(
            query_embeddings=[query_vec],
            n_results=self._fetch_k,
            include=["documents", "metadatas", "embeddings"],
            **filters,
        )
        return self._select(result, query_vec, k)

    def _retrieve_hybrid(
        self,
        question: str,
        query_vec: np.ndarray,
        documents: list[str] | None,
        k: int,
        table: _ChunkTable,
    ) -> list[Chunk]:
        """Dense + BM25 over every chunk of the routed documents, fused by reciprocal rank.

        The fused score is also MMR's relevance term: with dense relevance, MMR would drop
        exactly the lexical hits that dense retrieval ranked low.
        """
        idx = table.indices(documents)
        if len(idx) == 0:
            return []
        q = query_vec / (np.linalg.norm(query_vec) or 1.0)
        dense = table.vectors[idx] @ q
        lexical = table.bm25.scores(question, idx)
        fused = reciprocal_rank_fusion(ranks(dense), ranks(lexical))
        seen: set[str] = set()
        pool = [
            int(i)
            for i in np.argsort(-fused, kind="stable")
            if not (table.texts[idx[i]].strip() in seen or seen.add(table.texts[idx[i]].strip()))
        ][: self._fetch_k]
        relevance = fused[pool]
        spread = relevance.max() - relevance.min()
        relevance = (relevance - relevance.min()) / (spread or 1.0)
        picked = mmr_select(
            query_vec, table.vectors[idx[pool]], k, self._mmr_lambda, relevance=relevance
        )
        return [
            chunk_from_record(table.texts[idx[pool[i]]], table.metas[idx[pool[i]]]) for i in picked
        ]

    def _route(self, query_vec: np.ndarray, routing: RoutingConfig) -> list[str] | None:
        """Routed document name(s); None if routing is a no-op for this index."""
        result = self._col.query(
            query_embeddings=[query_vec],
            n_results=routing.candidates,
            include=["metadatas", "distances"],
        )
        sources = [str(m.get("source", "")) for m in result["metadatas"][0]]
        if not any(sources):  # index built before multi-document support: nothing to route
            return None
        similarities = [1.0 - d for d in result["distances"][0]]  # cosine space
        documents = route_documents(sources, similarities, routing.second_document_ratio)
        log.debug("routed to documents=%s", documents)
        return documents

    def _select(self, result: Any, query_vec: np.ndarray, k: int) -> list[Chunk]:
        """MMR over a Chroma query result."""
        docs, metas = result["documents"][0], result["metadatas"][0]
        vectors = np.asarray(result["embeddings"][0], dtype=np.float64)

        # Drop exact duplicates (overlap at page boundaries produced them in the notebook).
        seen: set[str] = set()
        unique = [i for i, d in enumerate(docs) if not (d.strip() in seen or seen.add(d.strip()))]
        if not unique:
            return []

        picked = mmr_select(query_vec, vectors[unique], k, self._mmr_lambda)
        return [chunk_from_record(docs[unique[i]], metas[unique[i]]) for i in picked]


def _source_filter(documents: list[str]) -> dict:
    if len(documents) == 1:
        return {"source": documents[0]}
    return {"source": {"$in": documents}}
