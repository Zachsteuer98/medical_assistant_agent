"""Maximal Marginal Relevance: balance relevance against redundancy among retrieved chunks."""

import numpy as np
from numpy.typing import NDArray


def _normalize(vectors: NDArray[np.float64]) -> NDArray[np.float64]:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def mmr_select(
    query: NDArray[np.float64], candidates: NDArray[np.float64], k: int, lambda_mult: float
) -> list[int]:
    """Return indices of up to k candidates. lambda_mult=1 is pure relevance, 0 pure diversity."""
    if len(candidates) == 0 or k <= 0:
        return []
    q = _normalize(query)
    docs = _normalize(candidates)
    relevance = docs @ q
    selected = [int(np.argmax(relevance))]
    remaining = [i for i in range(len(docs)) if i != selected[0]]
    while remaining and len(selected) < k:
        redundancy = (docs[remaining] @ docs[selected].T).max(axis=1)
        scores = lambda_mult * relevance[remaining] - (1 - lambda_mult) * redundancy
        best = remaining[int(np.argmax(scores))]
        selected.append(best)
        remaining.remove(best)
    return selected
