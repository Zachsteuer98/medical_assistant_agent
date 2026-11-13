"""Lexical (BM25) scoring and rank fusion for hybrid retrieval.

Dense MiniLM embeddings miss exact clinical vocabulary: for "maintenance inhaler for COPD
with moderate to severe symptom burden" the recommendation chunk ("... LABA/LAMA over
monotherapy") ranked ~150th among the COPD guideline's chunks, while BM25 ranks it near the
top. Hand-rolled (~40 lines) rather than a new dependency.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

# Standard BM25 parameters (Robertson & Zaragoza).
BM25_K1 = 1.2
BM25_B = 0.75
# Reciprocal rank fusion constant (Cormack et al., 2009): damps the head of each ranking so
# neither retriever dominates; 60 is the published default and was not tuned here.
RRF_K = 60
# Keeps drug-class names such as "laba/lama" and "glp-1" as single terms.
_TOKEN = re.compile(r"[a-z0-9]+(?:[/-][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    """Okapi BM25 over a fixed list of texts; corpus statistics cover every text."""

    def __init__(self, texts: Sequence[str]):
        self._term_counts = [Counter(tokenize(t)) for t in texts]
        self._lengths = np.array([sum(c.values()) for c in self._term_counts], dtype=np.float64)
        self._avg_length = float(self._lengths.mean()) if len(texts) else 0.0
        self._doc_freq = Counter(term for counts in self._term_counts for term in counts)
        self._n = len(texts)

    def _idf(self, term: str) -> float:
        df = self._doc_freq[term]
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def scores(self, query: str, indices: Sequence[int]) -> NDArray[np.float64]:
        """BM25 score of each text in `indices` (same order) for the query."""
        terms = [(t, self._idf(t)) for t in set(tokenize(query)) if t in self._doc_freq]
        out = np.zeros(len(indices))
        for row, i in enumerate(indices):
            counts = self._term_counts[i]
            norm = BM25_K1 * (1 - BM25_B + BM25_B * self._lengths[i] / self._avg_length)
            for term, idf in terms:
                tf = counts.get(term, 0)
                if tf:
                    out[row] += idf * tf * (BM25_K1 + 1) / (tf + norm)
        return out


def ranks(scores: NDArray[np.float64]) -> NDArray[np.int64]:
    """0-based rank of each score (0 = highest); ties keep input order."""
    order = np.argsort(-scores, kind="stable")
    out = np.empty(len(scores), dtype=np.int64)
    out[order] = np.arange(len(scores))
    return out


def reciprocal_rank_fusion(*rankings: NDArray[np.int64], k: int = RRF_K) -> NDArray[np.float64]:
    """Sum of 1 / (k + rank + 1) over rankings of the same items."""
    return sum((1.0 / (k + r + 1) for r in rankings), start=np.zeros(len(rankings[0])))
