"""Evaluation harness logic: corpus selection, retrieval hits, correctness, summaries.

No OpenAI: the judge is a fake."""

import pytest

from app.corpora import get_corpus
from app.rag.service import AssistantService
from app.rag.store import Chunk
from evaluation.judge import METRICS, CorrectnessVerdict, Verdict
from evaluation.public_queries import PUBLIC_QUERIES
from evaluation.queries import QUERIES, EvalQuery
from evaluation.run import (
    EXPERIMENTS,
    NOT_APPLICABLE,
    QUERY_SETS,
    Job,
    RunConfig,
    correctness_table,
    experiment_corpus,
    has_retrieval_labels,
    per_query_table,
    retrieval_hits,
    run_one,
    summarize,
)
from tests.fakes import MULTI_CORPUS, FakeLLM, FakeRetriever

DIABETES = "Guideline for Diabetes (2023)"
LABELLED = EvalQuery(
    "T1",
    "Diabetes",
    "A1c goal?",
    expected_source="Diabetes",
    expected_pages=(5,),
    expected_facts=("A1c 7-8% (Rec 1).", "Individualize (Rec 2)."),
)
OUT_OF_SCOPE = EvalQuery("T2", "Out of scope", "Pneumonia antibiotics?", answerable=False)
RAG = RunConfig("RAG", "multi", 200, 2, mode="rag", corpus="multi")
PLAIN = RunConfig("Plain", "multi", 200, 2, mode="plain_llm", corpus="multi")


class FakeJudge:
    def __init__(self, correctness: CorrectnessVerdict | None = None):
        self.contexts: list[str] = []
        self.correctness_calls: list[tuple[str, tuple[str, ...], str]] = []
        self._correctness = correctness or CorrectnessVerdict(("yes", "partly"), False, "", "ok")

    def rate(self, metric: str, question: str, context: str, answer: str) -> Verdict:
        self.contexts.append(context)
        return Verdict(4, "ok")

    def grade_correctness(
        self, question: str, source: str, facts: tuple[str, ...], answer: str
    ) -> CorrectnessVerdict:
        self.correctness_calls.append((source, facts, answer))
        return self._correctness


def _job(cfg: RunConfig, query: EvalQuery, chunks: list[Chunk], answer: str) -> Job:
    retriever, llm = FakeRetriever(chunks), FakeLLM(answer)
    svc = AssistantService(retriever, llm, MULTI_CORPUS, cfg.k)
    return Job(cfg, svc, retriever, llm, query, MULTI_CORPUS, labelled=True)


# --- corpus / query-set selection -------------------------------------------------------


def test_merck_experiments_still_use_merck_corpus_and_queries():
    for name in ("chunk_size", "approach"):
        assert experiment_corpus(EXPERIMENTS[name]) == "merck"
    assert QUERY_SETS["merck"] is QUERIES
    assert not has_retrieval_labels(QUERIES)


def test_public_experiment_compares_same_approaches_on_public_corpus():
    public, merck = EXPERIMENTS["public_approach"], EXPERIMENTS["approach"]
    assert experiment_corpus(public) == "public"
    assert [(c.name, c.mode, c.k, c.chunk_tokens) for c in public] == [
        (c.name, c.mode, c.k, c.chunk_tokens) for c in merck
    ]
    assert {c.collection for c in public} == {"public"}


def test_experiment_spanning_two_corpora_is_rejected():
    with pytest.raises(ValueError, match="exactly one corpus"):
        experiment_corpus((RAG, RunConfig("x", "merck", 200, 5)))


# --- public query set ground truth ------------------------------------------------------


def test_public_query_labels_point_at_real_content_pages():
    corpus = get_corpus("public")
    docs = {d.label: d for d in corpus.documents}
    for q in PUBLIC_QUERIES:
        if not q.answerable:
            assert not q.has_retrieval_labels, q.id
            continue
        doc = docs[q.expected_source]
        assert q.expected_pages, q.id
        for page in q.expected_pages:
            assert page <= doc.expected_pages and doc.is_content_page(page), (q.id, page)


def test_public_query_set_shape():
    ids = [q.id for q in PUBLIC_QUERIES]
    assert len(set(ids)) == len(ids)
    covered = {q.expected_source for q in PUBLIC_QUERIES if q.answerable}
    assert len(covered) == len(get_corpus("public").documents)
    assert 2 <= sum(not q.answerable for q in PUBLIC_QUERIES) <= 3


# --- retrieval hits ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("retrieved", "expected"),
    [
        ([("Diabetes", 5)], (True, True)),
        ([("Diabetes", 9), ("HTN", 5)], (True, False)),  # right page number, wrong guideline
        ([("HTN", 5)], (False, False)),
        ([], (False, False)),
    ],
)
def test_retrieval_hits(retrieved, expected):
    assert retrieval_hits(LABELLED, retrieved) == expected


def test_run_one_scores_rag_hits_and_judges_real_context():
    chunks = [
        Chunk("A1c 7-8%.", 5, DIABETES),
        Chunk("BP text.", 3, "Guideline for Hypertension (2026)"),
    ]
    judge = FakeJudge()
    row = run_one(_job(RAG, LABELLED, chunks, "7-8% [Source: Diabetes, Page: 5]"), judge)
    assert (row["guideline_hit"], row["page_hit"]) == (True, True)
    assert row["retrieved_sources"] == "Diabetes p5 | HTN p3"
    assert row["cites_pages"] and row["answered_from_context"]
    assert len(judge.contexts) == len(METRICS)
    assert all("A1c 7-8%." in c for c in judge.contexts)


def test_run_one_leaves_hits_empty_for_non_rag_and_unlabelled_queries():
    chunks = [Chunk("A1c 7-8%.", 5, DIABETES)]
    plain = run_one(_job(PLAIN, LABELLED, chunks, "Aim for 7%."), FakeJudge())
    oos = run_one(_job(RAG, OUT_OF_SCOPE, chunks, "x"), FakeJudge())
    for row in (plain, oos):
        assert (row["guideline_hit"], row["page_hit"]) == (None, None)
    assert plain["context_relevance"] is None


def test_run_one_grades_correctness_against_facts_for_every_mode():
    chunks = [Chunk("A1c 7-8%.", 5, DIABETES)]
    for cfg in (RAG, PLAIN):
        judge = FakeJudge()
        row = run_one(_job(cfg, LABELLED, chunks, "Aim for 7-8%."), judge)
        # The full document name is passed (not the short label), and no context is involved.
        assert judge.correctness_calls == [(DIABETES, LABELLED.expected_facts, "Aim for 7-8%.")]
        assert (row["correctness_grade"], row["correctness"], row["fact_coverage"]) == (
            "partial",
            3,
            0.75,
        )
        assert row["fact_labels"] == "yes partly" and row["contradiction"] is False


def test_run_one_skips_correctness_for_out_of_scope_queries():
    judge = FakeJudge()
    row = run_one(_job(RAG, OUT_OF_SCOPE, [Chunk("x", 1, DIABETES)], "x"), judge)
    assert judge.correctness_calls == []
    assert row["correctness"] is None and row["correctness_grade"] == ""


# --- summaries --------------------------------------------------------------------------


def _row(config, query_id, answerable, answered, guideline_hit=None, page_hit=None, grade=None):
    graded = grade is not None
    return {
        "correctness": {"pass": 5, "partial": 3, "fail": 1}.get(grade),
        "correctness_grade": grade or "",
        "fact_coverage": {"pass": 1.0, "partial": 0.5, "fail": 0.0}.get(grade),
        "contradiction": grade == "fail" if graded else None,
        "config": config,
        "query_id": query_id,
        "answerable": answerable,
        "answered_from_context": answered,
        "cites_pages": answered,
        "latency_s": 1.0,
        "guideline_hit": guideline_hit,
        "page_hit": page_hit,
        **dict.fromkeys(METRICS, 5),
    }


def test_summarize_reports_hit_rates_and_refusals_only_when_tracked():
    rows = [
        _row("RAG", "A", True, True, True, True, grade="pass"),
        _row("RAG", "B", True, False, True, False, grade="fail"),
        _row("RAG", "C", False, False),
        _row("Plain", "A", True, True, grade="partial"),
        _row("Plain", "B", True, True, grade="partial"),
        _row("Plain", "C", False, True),
    ]
    rag, plain = summarize(rows, (RAG, PLAIN), labelled=True)
    assert (rag["guideline_hit_rate"], rag["page_hit_rate"]) == ("2/2", "1/2")
    assert (rag["correct_refusals"], rag["unwarranted_refusals"]) == ("1/1", "1/2")
    assert plain["page_hit_rate"] == NOT_APPLICABLE
    assert plain["correct_refusals"] == "0/1"
    assert (rag["correctness"], rag["pass/partial/fail"], rag["mean_fact_coverage"]) == (
        3,
        "1/0/1",
        0.5,
    )
    assert (plain["correctness"], plain["pass/partial/fail"]) == (3, "0/2/0")

    untracked = summarize(rows, (RAG,))[0]
    assert "page_hit_rate" not in untracked and "correctness" not in untracked


def test_correctness_table_marks_contradictions_and_skips_out_of_scope():
    rows = [_row("RAG", "T1", True, True, grade="fail"), _row("RAG", "T2", False, False)]
    lines = correctness_table(rows, ["RAG"], (LABELLED, OUT_OF_SCOPE))
    assert lines == ["| query | RAG |", "|---|---|", "| T1 Diabetes | fail 0.00 ! |"]


def test_every_answerable_public_query_has_tagged_reference_facts():
    for q in PUBLIC_QUERIES:
        if not q.answerable:
            assert not q.expected_facts, q.id
            continue
        assert 1 <= len(q.expected_facts) <= 3, q.id
        assert all("(Rec" in fact for fact in q.expected_facts), q.id


def test_per_query_table_adds_hit_column_for_labelled_sets():
    rows = [_row("RAG", "T1", True, True, True, False), _row("RAG", "T2", False, False)]
    lines = per_query_table(rows, ["RAG"], (LABELLED, OUT_OF_SCOPE))
    assert lines[0] == "| query | RAG | RAG retrieval hit (guideline/page) |"
    assert lines[2] == "| T1 Diabetes | 5/5/5 | yes/no |"
    assert lines[3] == "| T2 Out of scope | 5/5/5 | – |"


def test_per_query_table_unchanged_for_unlabelled_sets():
    rows = [_row("RAG", "T2", False, False)]
    assert per_query_table(rows, ["RAG"], (OUT_OF_SCOPE,))[0] == "| query | RAG |"
