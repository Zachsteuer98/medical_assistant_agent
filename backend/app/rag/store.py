"""Chroma-backed vector store: index building (ingest) and MMR retrieval (serving)."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.rag.mmr import mmr_select

ADD_BATCH_SIZE = 256


class IndexNotReadyError(RuntimeError):
    """The vector collection for the configured corpus has not been built."""


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int  # 1-based PDF page


class Retriever(Protocol):
    def retrieve(self, question: str, k: int) -> list[Chunk]: ...

    def count(self) -> int: ...


def _client(chroma_dir: Path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=str(chroma_dir), settings=ChromaSettings(anonymized_telemetry=False)
    )


def build_index(chroma_dir: Path, collection: str, chunks: Sequence[Chunk]) -> int:
    """(Re)create the collection from scratch so re-ingesting is idempotent."""
    client = _client(chroma_dir)
    if collection in [c.name for c in client.list_collections()]:
        client.delete_collection(collection)
    col = client.create_collection(
        collection,
        embedding_function=DefaultEmbeddingFunction(),  # all-MiniLM-L6-v2 (ONNX), 384-d
        configuration={"hnsw": {"space": "cosine"}},
    )
    for start in range(0, len(chunks), ADD_BATCH_SIZE):
        batch = chunks[start : start + ADD_BATCH_SIZE]
        col.add(
            ids=[f"{collection}-{start + i}" for i in range(len(batch))],
            documents=[c.text for c in batch],
            metadatas=[{"page": c.page} for c in batch],
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
        return [Chunk(text=docs[unique[i]], page=int(metas[unique[i]]["page"])) for i in picked]
