import numpy as np

from app.rag.mmr import mmr_select


def test_first_pick_is_most_relevant():
    query = np.array([1.0, 0.0])
    docs = np.array([[0.0, 1.0], [1.0, 0.1], [0.5, 0.5]])
    assert mmr_select(query, docs, k=1, lambda_mult=0.7) == [1]


def test_prefers_diverse_over_near_duplicate():
    query = np.array([1.0, 0.2])
    docs = np.array([[1.0, 0.2], [1.0, 0.21], [0.6, 0.8]])  # 0 and 1 near-identical
    assert mmr_select(query, docs, k=2, lambda_mult=0.3) == [0, 2]
    assert mmr_select(query, docs, k=2, lambda_mult=1.0) == [0, 1]  # pure relevance


def test_handles_empty_and_k_larger_than_candidates():
    assert mmr_select(np.array([1.0]), np.empty((0, 1)), k=3, lambda_mult=0.5) == []
    assert sorted(mmr_select(np.array([1.0, 0]), np.eye(2), k=5, lambda_mult=0.5)) == [0, 1]
