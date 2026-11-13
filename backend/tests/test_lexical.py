from pathlib import Path

import numpy as np
import pytest

from app import main
from app.config import Settings
from app.corpora import get_corpus
from app.rag import store
from app.rag.lexical import BM25Index, ranks, reciprocal_rank_fusion, tokenize
from app.rag.mmr import mmr_select
from app.rag.routing import RoutingConfig
from app.rag.store import ChromaRetriever, Chunk, build_index
from tests.test_store import TinyEmbedding

# --- BM25 and fusion (pure) -------------------------------------------------------------


def test_tokenize_keeps_drug_class_names_whole():
    assert tokenize("LABA/LAMA over GLP-1 RA.") == ["laba/lama", "over", "glp-1", "ra"]


def test_bm25_prefers_the_text_with_the_rare_query_terms():
    texts = [
        "copd exacerbation sidebar maintenance inhalers",
        "moderate to severe symptom burden laba/lama over monotherapy",
        "copd background description",
    ]
    scores = BM25Index(texts).scores("COPD moderate to severe symptom burden", [0, 1, 2])
    assert int(np.argmax(scores)) == 1


def test_bm25_scores_only_requested_indices_in_order_and_zero_without_overlap():
    index = BM25Index(["alpha beta", "gamma", "beta beta"])
    scores = index.scores("beta", [2, 1])
    assert scores[0] > 0 and scores[1] == 0


def test_ranks_break_ties_by_position():
    assert ranks(np.array([0.5, 0.9, 0.5])).tolist() == [1, 0, 2]


def test_rrf_rewards_items_ranked_well_by_both_retrievers():
    dense = np.array([0, 1, 2])  # item 0 best dense
    lexical = np.array([2, 0, 1])  # item 1 best lexical
    fused = reciprocal_rank_fusion(dense, lexical, k=60)
    assert fused[1] > fused[2]  # 2nd + 1st beats 3rd + 2nd
    assert fused[0] == pytest.approx(1 / 61 + 1 / 63)


def test_mmr_uses_supplied_relevance_instead_of_query_cosine():
    query = np.array([1.0, 0.0])
    candidates = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert mmr_select(query, candidates, 1, 0.7)[0] == 0
    assert mmr_select(query, candidates, 1, 0.7, relevance=np.array([0.0, 1.0]))[0] == 1


# --- hybrid retriever end to end (tiny deterministic embedding) --------------------------


@pytest.fixture
def tiny_embedding(monkeypatch: pytest.MonkeyPatch) -> TinyEmbedding:
    monkeypatch.setattr(store, "DefaultEmbeddingFunction", TinyEmbedding)
    return TinyEmbedding()


def test_hybrid_brings_in_a_lexical_match_that_dense_ranks_last(tmp_path: Path, tiny_embedding):
    """Regression (P08): the recommendation chunk was ~150th by dense similarity alone."""
    question = "copd inhaler for symptom burden"
    # TinyEmbedding is driven by the leading characters, so these look like the question...
    decoys = [Chunk(f"copd irrelevant filler {i}", i + 1, "COPD") for i in range(6)]
    # ...and this one does not, but it shares the rare terms.
    answer = Chunk("zz LABA/LAMA for moderate symptom burden", 40, "COPD")
    other = [Chunk(f"asthma unrelated {i}", 50 + i, "Asthma") for i in range(2)]
    build_index(tmp_path, "hybrid-test", decoys + [answer] + other, tiny_embedding)
    routing = RoutingConfig(candidates=9)

    dense = ChromaRetriever(tmp_path, "hybrid-test", 5, 0.7, routing).retrieve(question, 4)
    hybrid = ChromaRetriever(tmp_path, "hybrid-test", 5, 0.7, routing, hybrid=True).retrieve(
        question, 4
    )

    assert answer not in dense
    assert answer in hybrid
    assert {c.source for c in hybrid} == {"COPD"}  # routing still applies


def test_hybrid_without_routing_is_rejected(tmp_path: Path, tiny_embedding):
    build_index(tmp_path, "hybrid-test", [Chunk("some chunk text", 1, "A")], tiny_embedding)
    with pytest.raises(ValueError, match="requires document routing"):
        ChromaRetriever(tmp_path, "hybrid-test", 4, 0.7, None, hybrid=True)


@pytest.mark.parametrize(("corpus", "expected"), [("merck", False), ("public", True)])
def test_build_service_enables_hybrid_only_for_multi_document_corpora(
    monkeypatch: pytest.MonkeyPatch, corpus: str, expected: bool
):
    captured: dict = {}

    class Recorder:
        def __init__(self, *args, **kwargs):
            captured.update(routing=args[4], hybrid=kwargs["hybrid"])

    monkeypatch.setattr(main, "ChromaRetriever", Recorder)
    main.build_service(Settings(corpus=corpus, route_by_document=True, hybrid_retrieval=True))
    assert captured["hybrid"] is expected
    assert (captured["routing"] is not None) is expected


def test_hybrid_and_rec_chunk_collection_are_production_defaults():
    assert Settings.model_fields["hybrid_retrieval"].default is True
    assert get_corpus("public").default_collection == "public_rec"
    assert get_corpus("merck").default_collection == "merck"  # existing index, no rebuild


@pytest.mark.parametrize(("corpus", "collection"), [("merck", "merck"), ("public", "public_rec")])
def test_build_service_serves_the_corpus_default_collection(
    monkeypatch: pytest.MonkeyPatch, corpus: str, collection: str
):
    captured: dict = {}

    class Recorder:
        def __init__(self, *args, **kwargs):
            captured["collection"] = args[1]

    monkeypatch.setattr(main, "ChromaRetriever", Recorder)
    main.build_service(Settings(corpus=corpus, collection=None))
    assert captured["collection"] == collection
    main.build_service(Settings(corpus=corpus, collection="override"))
    assert captured["collection"] == "override"
