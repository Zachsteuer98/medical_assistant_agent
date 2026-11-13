from pathlib import Path

import pytest

from app.config import Settings
from app.main import routing_config
from app.rag import store
from app.rag.routing import (
    DEFAULT_SECOND_DOCUMENT_RATIO,
    RoutingConfig,
    document_scores,
    route_documents,
)
from app.rag.store import ChromaRetriever, Chunk, build_index
from tests.fakes import MULTI_CORPUS, TEST_CORPUS
from tests.test_store import TinyEmbedding

RATIO = DEFAULT_SECOND_DOCUMENT_RATIO
COLLECTION = "routing-test"

# --- route_documents (pure) -------------------------------------------------------------


def test_scores_sum_similarity_per_document():
    assert document_scores(["A", "B", "A"], [0.5, 0.25, 0.75]) == {"A": 1.25, "B": 0.25}


def test_picks_only_the_top_document_when_runner_up_is_outside_the_margin():
    # Shape of the P07 leak: COPD chunks scored ~0.3 of the asthma guideline.
    sources = ["Asthma"] * 3 + ["COPD"]
    assert route_documents(sources, [0.7, 0.7, 0.7, 0.68], RATIO) == ["Asthma"]


def test_includes_runner_up_within_the_margin_best_first():
    # Shape of P09: CKD and diabetes guidelines score almost the same.
    sources = ["Diabetes", "CKD", "Diabetes", "CKD"]
    assert route_documents(sources, [0.76, 0.73, 0.7, 0.7], RATIO) == ["Diabetes", "CKD"]


def test_runner_up_exactly_at_the_margin_is_included():
    assert route_documents(["A", "B"], [0.8, 0.4], 0.5) == ["A", "B"]


def test_never_routes_to_more_than_two_documents():
    assert route_documents(["A", "B", "C"], [0.5, 0.5, 0.5], RATIO) == ["A", "B"]


def test_single_document_routes_to_itself():
    assert route_documents(["Only"] * 4, [0.9, 0.8, 0.7, 0.6], RATIO) == ["Only"]


def test_empty_candidates_route_nowhere():
    assert route_documents([], [], RATIO) == []


def test_ties_are_broken_by_name_regardless_of_candidate_order():
    a_first = route_documents(["Zeta", "Alpha", "Mid"], [0.5, 0.5, 0.5], RATIO)
    z_first = route_documents(["Mid", "Alpha", "Zeta"], [0.5, 0.5, 0.5], RATIO)
    assert a_first == z_first == ["Alpha", "Mid"]
    assert route_documents(["B", "A"], [0.4, 0.4], 1.0) == ["A", "B"]


def test_non_positive_top_score_keeps_only_the_top_document():
    assert route_documents(["A", "B"], [-0.1, -0.2], RATIO) == ["A"]


def test_mismatched_inputs_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        route_documents(["A"], [0.1, 0.2], RATIO)


@pytest.mark.parametrize(
    "kwargs", [{"candidates": 0}, {"second_document_ratio": 0.0}, {"second_document_ratio": 1.5}]
)
def test_invalid_routing_config_fails_fast(kwargs):
    with pytest.raises(ValueError):
        RoutingConfig(**kwargs)


# --- wiring: routing only ever applies to multi-document corpora ------------------------


def test_routing_config_is_none_for_single_document_corpus_even_when_enabled():
    assert routing_config(Settings(route_by_document=True), TEST_CORPUS) is None
    assert routing_config(Settings(), TEST_CORPUS, enabled=True) is None


def test_routing_config_follows_setting_for_multi_document_corpus():
    settings = Settings(
        route_by_document=True, routing_candidates=7, routing_second_document_ratio=0.6
    )
    assert routing_config(settings, MULTI_CORPUS) == RoutingConfig(7, 0.6)
    assert routing_config(Settings(route_by_document=False), MULTI_CORPUS) is None


def test_routing_config_explicit_override_beats_setting():
    assert routing_config(Settings(route_by_document=True), MULTI_CORPUS, enabled=False) is None
    assert routing_config(Settings(route_by_document=False), MULTI_CORPUS, enabled=True)


# --- ChromaRetriever end to end (tiny deterministic embedding, no model download) -------


@pytest.fixture
def tiny_embedding(monkeypatch: pytest.MonkeyPatch) -> TinyEmbedding:
    monkeypatch.setattr(store, "DefaultEmbeddingFunction", TinyEmbedding)
    return TinyEmbedding()


def _index(tmp_path: Path, chunks: list[Chunk], embed: TinyEmbedding) -> Path:
    build_index(tmp_path, COLLECTION, chunks, embed)
    return tmp_path


def test_routed_retrieval_drops_chunks_from_other_documents(tmp_path, tiny_embedding):
    question = "asthma inhaler regimen"
    on_topic = [Chunk(f"asthma inhaler regimen {i}", i + 1, "Asthma") for i in range(4)]
    leak = [Chunk("zzzzzzzz unrelated text", 9, "COPD")]
    root = _index(tmp_path, on_topic + leak, tiny_embedding)

    unrouted = ChromaRetriever(root, COLLECTION, fetch_k=5, mmr_lambda=0.7)
    routed = ChromaRetriever(root, COLLECTION, 5, 0.7, RoutingConfig(candidates=5))

    assert "COPD" in {c.source for c in unrouted.retrieve(question, 5)}
    assert {c.source for c in routed.retrieve(question, 5)} == {"Asthma"}


def test_routing_is_a_no_op_on_a_single_document_index(tmp_path, tiny_embedding):
    """An index without source names (Merck) must retrieve exactly as before."""
    chunks = [Chunk(f"chunk {i} about sepsis care", i + 1) for i in range(6)]
    root = _index(tmp_path, chunks, tiny_embedding)

    plain = ChromaRetriever(root, COLLECTION, 6, 0.7).retrieve("sepsis care", 4)
    routed = ChromaRetriever(root, COLLECTION, 6, 0.7, RoutingConfig()).retrieve("sepsis care", 4)

    assert routed == plain
    assert len(plain) == 4


def test_routing_is_on_by_default_but_still_skips_single_document_corpora():
    assert Settings.model_fields["route_by_document"].default is True
    assert routing_config(Settings(route_by_document=True), TEST_CORPUS) is None
