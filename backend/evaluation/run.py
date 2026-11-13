"""Run an evaluation experiment.

    uv run python -m evaluation.run --experiment chunk_size
    uv run python -m evaluation.run --experiment public_approach

Each experiment runs on one corpus; the corpus selects the query set (QUERY_SETS).

Writes full rows (incl. retrieved licensed text) to eval/results/ (git-ignored) and
numbers-only summaries + charts to eval/ (safe to commit).
"""

import argparse
import csv
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from openai import OpenAI

from app.config import REPO_ROOT, get_settings
from app.corpora import CorpusSpec, get_corpus
from app.main import routing_config
from app.rag.llm import ChatModel, OpenAIChatModel
from app.rag.prompts import FALLBACK_ANSWER
from app.rag.service import AssistantService
from app.rag.store import ChromaRetriever
from evaluation.baselines import NOTEBOOK_SYSTEM_PROMPT
from evaluation.judge import GRADE_SCORES, METRICS, Judge
from evaluation.public_queries import PUBLIC_QUERIES
from evaluation.queries import QUERIES, EvalQuery

JUDGE_MODEL = "gpt-4o"
WORKERS = 4
FETCH_K_MULTIPLIER = 4  # MMR candidate pool size relative to k
EVAL_DIR = REPO_ROOT / "eval"
log = logging.getLogger("eval")
NOT_APPLICABLE = "n/a"
QUERY_SETS: dict[str, tuple[EvalQuery, ...]] = {"merck": QUERIES, "public": PUBLIC_QUERIES}

# rag: production pipeline. plain_llm / prompted: answer without retrieval; manual excerpts are
# still retrieved, but only so the judge can check traceability to the trusted source.
Mode = Literal["rag", "plain_llm", "prompted"]
_NON_RAG_SYSTEM_PROMPTS = {"plain_llm": "", "prompted": NOTEBOOK_SYSTEM_PROMPT}


@dataclass(frozen=True)
class RunConfig:
    name: str
    collection: str
    chunk_tokens: int
    k: int
    mode: Mode = "rag"
    corpus: str = "merck"
    # Guideline routing (multi-document corpora only); set explicitly so a run never depends
    # on the ROUTE_BY_DOCUMENT environment setting.
    route: bool = False
    # BM25 + dense fusion inside the routed guideline(s); requires route=True.
    hybrid: bool = False


@dataclass(frozen=True)
class Job:
    cfg: RunConfig
    svc: AssistantService
    retriever: ChromaRetriever
    llm: ChatModel
    query: EvalQuery
    corpus: CorpusSpec
    # True when the query set carries ground truth (expected source, pages, facts); adds
    # retrieval-hit and correctness columns to the rows.
    labelled: bool = False


def metrics_for(cfg: RunConfig) -> tuple[str, ...]:
    # Context relevance scores retrieval quality, which only exists for RAG answers.
    return METRICS if cfg.mode == "rag" else tuple(m for m in METRICS if m != "context_relevance")


EXPERIMENTS: dict[str, tuple[RunConfig, ...]] = {
    "chunk_size": (
        RunConfig("1000-token chunks, k=5 (notebook baseline)", "merck_c1000", 1000, 5),
        RunConfig("200-token chunks, k=5", "merck", 200, 5),
        RunConfig("200-token chunks, k=25 (equal context budget)", "merck", 200, 25),
    ),
    "approach": (
        RunConfig("Plain LLM", "merck", 200, 5, mode="plain_llm"),
        RunConfig("Prompt-engineered LLM", "merck", 200, 5, mode="prompted"),
        RunConfig("RAG (production)", "merck", 200, 5, mode="rag"),
    ),
    # Same three approaches on the hosted demo's corpus, plus RAG without guideline routing
    # (the production retriever before routing) to keep the comparison visible.
    "public_approach": (
        RunConfig("Plain LLM", "public", 200, 5, mode="plain_llm", corpus="public"),
        RunConfig("Prompt-engineered LLM", "public", 200, 5, mode="prompted", corpus="public"),
        RunConfig("RAG (no routing)", "public", 200, 5, mode="rag", corpus="public"),
        RunConfig(
            "RAG (guideline routing)",
            "public",
            200,
            5,
            mode="rag",
            corpus="public",
            route=True,
        ),
        # Production: recommendation-aware chunks (collection public_rec) + BM25/dense fusion.
        RunConfig(
            "RAG (production, rec chunks + hybrid)",
            "public_rec",
            200,
            5,
            mode="rag",
            corpus="public",
            route=True,
            hybrid=True,
        ),
    ),
}

# Caveats printed under the summary table so they survive re-runs.
EXPERIMENT_NOTES: dict[str, str] = {
    "public_approach": (
        "Corpus: 10 VA/DoD Clinical Practice Guidelines (`public`). These numbers are not "
        "directly comparable to the Merck results (summary_approach.md): different corpus, "
        "different query set, and narrower guideline-specific questions. Retrieval hit rates "
        "count RAG answers whose top-k context contains the expected guideline (guideline hit) "
        "or a chunk from that guideline's expected recommendation/discussion pages (page hit). "
        "Correctness is judged against 1-3 reference facts per question, without the retrieved "
        "context: pass = every fact fully stated and no contradiction; partial = some facts "
        "missing or incomplete, no contradiction; fail = a contradiction (conflicting advice, or "
        "conflicting advice imported from another guideline) or no fact covered. In means, "
        "pass = 5, partial = 3, fail = 1. Written analysis and manual review: "
        "[analysis_public.md](analysis_public.md)."
    ),
}


def experiment_corpus(configs: tuple[RunConfig, ...]) -> str:
    corpora = {cfg.corpus for cfg in configs}
    if len(corpora) != 1:
        raise ValueError(f"An experiment must use exactly one corpus; got {sorted(corpora)}")
    return corpora.pop()


def has_retrieval_labels(queries: tuple[EvalQuery, ...]) -> bool:
    return any(q.has_retrieval_labels for q in queries)


def retrieval_hits(query: EvalQuery, retrieved: list[tuple[str, int]]) -> tuple[bool, bool]:
    """(guideline hit, page hit) for retrieved (citation label, page) pairs."""
    from_source = [page for label, page in retrieved if label == query.expected_source]
    return bool(from_source), any(page in query.expected_pages for page in from_source)


def answer(job: Job) -> tuple[str, list, float]:
    started = time.perf_counter()
    if job.cfg.mode == "rag":
        response, chunks = job.svc.ask_with_context(job.query.question)
        text = response.answer
    else:
        text = job.llm.complete(_NON_RAG_SYSTEM_PROMPTS[job.cfg.mode], job.query.question)
        chunks = []
    latency_s = time.perf_counter() - started
    if not chunks:  # judge reference for non-RAG answers (not timed)
        chunks = job.retriever.retrieve(job.query.question, job.cfg.k)
    return text, chunks, latency_s


def run_one(job: Job, judge: Judge) -> dict:
    cfg, q = job.cfg, job.query
    text, chunks, latency_s = answer(job)
    context = job.svc.format_context(chunks)
    row = {
        "config": cfg.name,
        "query_id": q.id,
        "category": q.category,
        "answerable": q.answerable,
        "question": q.question,
        "answered_from_context": FALLBACK_ANSWER not in text,
        "cites_pages": bool(job.svc.cited_keys(text)),
        "retrieved_pages": " ".join(str(c.page) for c in chunks),
        "context_tokens_approx": len(context) // 4,
        "latency_s": round(latency_s, 2),
        "answer": text,
        "context": context,
    }
    if job.labelled:
        row.update(retrieval_columns(job, chunks))
    for metric in METRICS:
        if metric in metrics_for(cfg):
            verdict = judge.rate(metric, q.question, context, text)
            row[metric], row[f"{metric}_rationale"] = verdict.score, verdict.rationale
        else:
            row[metric], row[f"{metric}_rationale"] = None, ""
    if job.labelled:
        row.update(correctness_columns(job, judge, text))
    log.info("done config=%r query=%s %s", cfg.name, q.id, {m: row[m] for m in METRICS})
    return row


def retrieval_columns(job: Job, chunks: list) -> dict:
    q = job.query
    retrieved = [(job.corpus.document_named(c.source).label, c.page) for c in chunks]
    row = {
        "expected_source": q.expected_source,
        "expected_pages": " ".join(map(str, q.expected_pages)),
        "retrieved_sources": " | ".join(f"{label} p{page}" for label, page in retrieved),
        "guideline_hit": None,
        "page_hit": None,
    }
    # Hits only mean something where retrieval fed the answer and ground truth exists.
    if job.cfg.mode == "rag" and q.has_retrieval_labels:
        row["guideline_hit"], row["page_hit"] = retrieval_hits(q, retrieved)
    return row


def correctness_columns(job: Job, judge: Judge, text: str) -> dict:
    q = job.query
    row: dict = {
        "correctness": None,
        "correctness_grade": "",
        "fact_coverage": None,
        "fact_labels": "",
        "contradiction": None,
        "contradiction_detail": "",
        "correctness_rationale": "",
    }
    if not q.expected_facts:  # out-of-scope probes are scored by the refusal check instead
        return row
    source = next(d.display_name for d in job.corpus.documents if d.label == q.expected_source)
    verdict = judge.grade_correctness(q.question, source, q.expected_facts, text)
    row.update(
        correctness=verdict.score,
        correctness_grade=verdict.grade,
        fact_coverage=round(verdict.coverage, 2),
        fact_labels=" ".join(verdict.fact_labels),
        contradiction=verdict.contradiction,
        contradiction_detail=verdict.contradiction_detail,
        correctness_rationale=verdict.rationale,
    )
    return row


def _hit_rate(rows: list[dict], column: str) -> str:
    scored = [r[column] for r in rows if r[column] is not None]
    return f"{sum(scored)}/{len(scored)}" if scored else NOT_APPLICABLE


def summarize(
    rows: list[dict], configs: tuple[RunConfig, ...], labelled: bool = False
) -> list[dict]:
    summary = []
    for cfg in configs:
        cfg_rows = [r for r in rows if r["config"] == cfg.name]
        answerable = [r for r in cfg_rows if r["answerable"]]
        out_of_scope = [r for r in cfg_rows if not r["answerable"]]
        entry: dict = {"config": cfg.name}
        for metric in METRICS:
            scores = [r[metric] for r in answerable if r[metric] is not None]
            entry[metric] = round(statistics.mean(scores), 2) if scores else NOT_APPLICABLE
        entry["page_cited_answers"] = (
            f"{sum(r['cites_pages'] for r in answerable)}/{len(answerable)}"
        )
        entry["correct_refusals"] = (
            f"{sum(not r['answered_from_context'] for r in out_of_scope)}/{len(out_of_scope)}"
        )
        if labelled:
            entry["guideline_hit_rate"] = _hit_rate(answerable, "guideline_hit")
            entry["page_hit_rate"] = _hit_rate(answerable, "page_hit")
            entry["unwarranted_refusals"] = (
                f"{sum(not r['answered_from_context'] for r in answerable)}/{len(answerable)}"
            )
            entry.update(correctness_summary(answerable))
        entry["mean_latency_s"] = round(statistics.mean(r["latency_s"] for r in cfg_rows), 1)
        summary.append(entry)
    return summary


def correctness_summary(answerable: list[dict]) -> dict:
    graded = [r for r in answerable if r["correctness"] is not None]
    if not graded:
        return dict.fromkeys(
            ("correctness", "pass/partial/fail", "mean_fact_coverage"), NOT_APPLICABLE
        )
    counts = "/".join(str(sum(r["correctness_grade"] == g for r in graded)) for g in GRADE_SCORES)
    return {
        "correctness": round(statistics.mean(r["correctness"] for r in graded), 2),
        "pass/partial/fail": counts,
        "mean_fact_coverage": round(statistics.mean(r["fact_coverage"] for r in graded), 2),
    }


# Column types for reading rows back from a results CSV (everything else stays a string).
_BOOL_COLUMNS = frozenset(
    {"answerable", "answered_from_context", "cites_pages", "guideline_hit", "page_hit"}
    | {"contradiction"}
)
_INT_COLUMNS = frozenset({*METRICS, "context_tokens_approx", "correctness"})
_FLOAT_COLUMNS = frozenset({"latency_s", "fact_coverage"})


def _parse_cell(column: str, value: str) -> object:
    if column not in _BOOL_COLUMNS | _INT_COLUMNS | _FLOAT_COLUMNS:
        return value
    if value == "":
        return None
    if column in _BOOL_COLUMNS:
        return value == "True"
    return int(value) if column in _INT_COLUMNS else float(value)


def load_rows(path: Path) -> list[dict]:
    """Rows of a results CSV written by write_outputs, with their original types."""
    with open(path, newline="") as f:
        return [{k: _parse_cell(k, v) for k, v in row.items()} for row in csv.DictReader(f)]


def select_configs(
    configs: tuple[RunConfig, ...], names: list[str] | None
) -> tuple[RunConfig, ...]:
    if not names:
        return configs
    unknown = set(names) - {c.name for c in configs}
    if unknown:
        raise ValueError(
            f"Unknown config(s) {sorted(unknown)}; expected {[c.name for c in configs]}"
        )
    return tuple(c for c in configs if c.name in names)


def reused_rows(previous: list[dict], configs: tuple[RunConfig, ...], ran: set[str]) -> list[dict]:
    """Rows of configs not re-run this time, taken from the previous results.

    Fails if a config has neither fresh nor previous rows, so a summary is never partial.
    """
    keep = [r for r in previous if r["config"] not in ran]
    missing = {c.name for c in configs} - ran - {r["config"] for r in keep}
    if missing:
        raise ValueError(f"No previous results for {sorted(missing)}; run them too")
    return [r for r in keep if r["config"] in {c.name for c in configs}]


def write_outputs(
    experiment: str,
    rows: list[dict],
    summary: list[dict],
    queries: tuple[EvalQuery, ...] = QUERIES,
    reused: tuple[str, ...] = (),
) -> None:
    (EVAL_DIR / "results").mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "charts").mkdir(parents=True, exist_ok=True)
    with open(EVAL_DIR / "results" / f"{experiment}.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # Numbers-only artifacts (no licensed text) — safe to commit.
    lines = [f"# Experiment: {experiment}", "", "Mean scores (1-5) over answerable queries.", ""]
    header = list(summary[0])
    lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(s[h]) for h in header) + " |" for s in summary]
    if experiment in EXPERIMENT_NOTES:
        lines += ["", EXPERIMENT_NOTES[experiment]]
    if reused:
        lines += ["", f"Rows reused from the previous run (not re-run): {', '.join(reused)}."]
    lines += ["", "## Per-query scores (context_relevance / groundedness / answer_relevance)", ""]
    lines += per_query_table(rows, [s["config"] for s in summary], queries)
    if any(q.expected_facts for q in queries):
        lines += ["", "## Per-query correctness (grade, fact coverage; ! = contradiction)", ""]
        lines += correctness_table(rows, [s["config"] for s in summary], queries)
    (EVAL_DIR / f"summary_{experiment}.md").write_text("\n".join(lines) + "\n")
    plot_summary(summary, EVAL_DIR / "charts" / f"{experiment}.png")


def per_query_table(
    rows: list[dict], configs: list[str], queries: tuple[EvalQuery, ...]
) -> list[str]:
    tracked = has_retrieval_labels(queries)
    extra = ["RAG retrieval hit (guideline/page)"] if tracked else []
    columns = ["query", *configs, *extra]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for q in queries:
        q_rows = {r["config"]: r for r in rows if r["query_id"] == q.id}
        cells = [
            "/".join("–" if q_rows[c][m] is None else str(q_rows[c][m]) for m in METRICS)
            for c in configs
        ]
        if tracked:
            cells.append(_hit_cell([q_rows[c] for c in configs]))
        lines.append(f"| {q.id} {q.category} | " + " | ".join(cells) + " |")
    return lines


def correctness_table(
    rows: list[dict], configs: list[str], queries: tuple[EvalQuery, ...]
) -> list[str]:
    lines = ["| query | " + " | ".join(configs) + " |", "|" + "---|" * (len(configs) + 1)]
    for q in queries:
        if not q.expected_facts:
            continue
        q_rows = {r["config"]: r for r in rows if r["query_id"] == q.id}
        cells = [
            f"{r['correctness_grade']} {r['fact_coverage']:.2f}"
            + (" !" if r["contradiction"] else "")
            for r in (q_rows[c] for c in configs)
        ]
        lines.append(f"| {q.id} {q.category} | " + " | ".join(cells) + " |")
    return lines


def _hit_cell(q_rows: list[dict]) -> str:
    scored = [r for r in q_rows if r["guideline_hit"] is not None]
    if not scored:
        return "–"
    return "/".join("yes" if scored[0][h] else "no" for h in ("guideline_hit", "page_hit"))


def plot_summary(summary: list[dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {
        "context_relevance": "Context relevance",
        "groundedness": "Groundedness",
        "answer_relevance": "Answer relevance",
        "correctness": "Correctness\n(pass=5, partial=3, fail=1)",
    }
    metrics = METRICS + (("correctness",) if "correctness" in summary[0] else ())
    width = 0.8 / len(summary)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    for i, s in enumerate(summary):
        xs = [j + i * width for j in range(len(metrics))]
        values = [s[m] if s[m] != NOT_APPLICABLE else 0 for m in metrics]
        bars = ax.bar(xs, values, width, label=s["config"])
        bar_text = ["n/a" if s[m] == NOT_APPLICABLE else f"{s[m]:.2f}" for m in metrics]
        ax.bar_label(bars, labels=bar_text, fontsize=8)
    ax.set_xticks([j + width * (len(summary) - 1) / 2 for j in range(len(metrics))])
    ax.set_xticklabels([labels[m] for m in metrics])
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Mean judge score (1-5)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=1)
    fig.tight_layout()
    fig.savefig(path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENTS), required=True)
    parser.add_argument(
        "--configs",
        nargs="+",
        help="Run only these config names; the others are reused from the previous results CSV",
    )
    args = parser.parse_args()

    settings = get_settings()
    configs = EXPERIMENTS[args.experiment]
    to_run = select_configs(configs, args.configs)
    previous_path = EVAL_DIR / "results" / f"{args.experiment}.csv"
    ran = {c.name for c in to_run}
    reused = reused_rows(load_rows(previous_path), configs, ran) if args.configs else []
    corpus_name = experiment_corpus(configs)
    corpus = get_corpus(corpus_name)
    queries = QUERY_SETS[corpus_name]
    labelled = has_retrieval_labels(queries)
    llm = OpenAIChatModel(
        settings.openai_api_key,
        settings.openai_base_url,
        settings.generator_model,
        settings.temperature,
        settings.max_tokens,
        settings.llm_timeout_s,
    )
    judge = Judge(
        OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, max_retries=5),
        JUDGE_MODEL,
    )
    jobs = []
    for cfg in to_run:
        retriever = ChromaRetriever(
            corpus.chroma_dir(settings.chroma_dir),
            cfg.collection,
            cfg.k * FETCH_K_MULTIPLIER,
            settings.mmr_lambda,
            routing_config(settings, corpus, cfg.route),
            hybrid=cfg.hybrid,
        )
        svc = AssistantService(retriever, llm, corpus, cfg.k)
        jobs += [Job(cfg, svc, retriever, llm, q, corpus, labelled) for q in queries]

    log.info("running %d answers, judged by %s", len(jobs), JUDGE_MODEL)
    with ThreadPoolExecutor(WORKERS) as pool:
        fresh = list(pool.map(lambda job: run_one(job, judge), jobs))
    order = {c.name: i for i, c in enumerate(configs)}
    rows = sorted(reused + fresh, key=lambda r: order[r["config"]])  # stable within config
    summary = summarize(rows, configs, labelled)
    reused_names = tuple(c.name for c in configs if c.name not in ran)
    write_outputs(args.experiment, rows, summary, queries, reused_names)
    for s in summary:
        log.info("summary %s", s)


if __name__ == "__main__":
    main()
