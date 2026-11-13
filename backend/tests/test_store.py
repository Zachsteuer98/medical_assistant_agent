import re
from pathlib import Path

import numpy as np
from chromadb import Documents, EmbeddingFunction, Embeddings

from app.rag.store import Chunk, _client, build_index

UUID_DIR = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TinyEmbedding(EmbeddingFunction[Documents]):
    """Deterministic 8-d embedding: no model download in tests."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [
            np.array([len(t) % 7 + 1, *map(float, t.encode()[:7].ljust(7, b"a"))]) for t in input
        ]

    @staticmethod
    def name() -> str:
        return "tiny-test"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "TinyEmbedding":
        return TinyEmbedding()


def segment_dirs(root: Path) -> set[str]:
    return {p.name for p in root.iterdir() if p.is_dir() and UUID_DIR.match(p.name)}


def chunks(n: int) -> list[Chunk]:
    return [Chunk(f"chunk number {i} text", i + 1, "Doc") for i in range(n)]


def test_rebuild_removes_old_segment_dir_but_not_other_collections(tmp_path: Path):
    """Regression: re-ingest leaked the previous HNSW directory (~10 MB) on every rebuild."""
    embed = TinyEmbedding()
    build_index(tmp_path, "other", chunks(5), embed)
    other_dirs = segment_dirs(tmp_path)
    build_index(tmp_path, "public", chunks(5), embed)
    first_build = segment_dirs(tmp_path) - other_dirs

    assert build_index(tmp_path, "public", chunks(3), embed) == 3

    after = segment_dirs(tmp_path)
    assert first_build and not (first_build & after)  # old public segment gone
    assert other_dirs <= after  # sibling collection untouched
    assert len(after) == len(other_dirs) + 1
    assert _client(tmp_path).get_collection("other").count() == 5
