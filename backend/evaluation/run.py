"""Run an evaluation experiment.

    uv run python -m evaluation.run --experiment chunk_size

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
from app.corpora import get_corpus
from app.rag.llm import ChatModel, OpenAIChatModel
from app.rag.prompts import FALLBACK_ANSWER
from app.rag.service import AssistantService
from app.rag.store import ChromaRetriever
from evaluation.baselines import NOTEBOOK_SYSTEM_PROMPT
from evaluation.judge import METRICS, Judge
from evaluation.queries import QUERIES, EvalQuery

JUDGE_MODEL = "gpt-4o"
WORKERS = 4
FETCH_K_MULTIPLIER = 4  # MMR candidate pool size relative to k
EVAL_DIR = REPO_ROOT / "eval"
log = logging.getLogger("eval")
NOT_APPLICABLE = "n/a"

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


@dataclass(frozen=True)
class Job:
    cfg: RunConfig
    svc: AssistantService
    retriever: ChromaRetriever
    llm: ChatModel
    query: EvalQuery


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
}


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
    for metric in METRICS:
        if metric in metrics_for(cfg):
            verdict = judge.rate(metric, q.question, context, text)
            row[metric], row[f"{metric}_rationale"] = verdict.score, verdict.rationale
        else:
            row[metric], row[f"{metric}_rationale"] = None, ""
    log.info("done config=%r query=%s %s", cfg.name, q.id, {m: row[m] for m in METRICS})
    return row


def summarize(rows: list[dict], configs: tuple[RunConfig, ...]) -> list[dict]:
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
        entry["mean_latency_s"] = round(statistics.mean(r["latency_s"] for r in cfg_rows), 1)
        summary.append(entry)
    return summary


def write_outputs(experiment: str, rows: list[dict], summary: list[dict]) -> None:
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
    lines += ["", "## Per-query scores (context_relevance / groundedness / answer_relevance)", ""]
    configs = [s["config"] for s in summary]
    lines += ["| query | " + " | ".join(configs) + " |", "|" + "---|" * (len(configs) + 1)]
    for q in QUERIES:
        cells = []
        for c in configs:
            r = next(r for r in rows if r["config"] == c and r["query_id"] == q.id)
            cells.append("/".join("–" if r[m] is None else str(r[m]) for m in METRICS))
        lines.append(f"| {q.id} {q.category} | " + " | ".join(cells) + " |")
    (EVAL_DIR / f"summary_{experiment}.md").write_text("\n".join(lines) + "\n")
    plot_summary(summary, EVAL_DIR / "charts" / f"{experiment}.png")


def plot_summary(summary: list[dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {
        "context_relevance": "Context relevance",
        "groundedness": "Groundedness",
        "answer_relevance": "Answer relevance",
    }
    width = 0.8 / len(summary)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    for i, s in enumerate(summary):
        xs = [j + i * width for j in range(len(METRICS))]
        values = [s[m] if s[m] != NOT_APPLICABLE else 0 for m in METRICS]
        bars = ax.bar(xs, values, width, label=s["config"])
        bar_text = ["n/a" if s[m] == NOT_APPLICABLE else f"{s[m]:.2f}" for m in METRICS]
        ax.bar_label(bars, labels=bar_text, fontsize=8)
    ax.set_xticks([j + width * (len(summary) - 1) / 2 for j in range(len(METRICS))])
    ax.set_xticklabels([labels[m] for m in METRICS])
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
    args = parser.parse_args()

    settings = get_settings()
    corpus = get_corpus(settings.corpus)
    configs = EXPERIMENTS[args.experiment]
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
    for cfg in configs:
        retriever = ChromaRetriever(
            corpus.chroma_dir(settings.chroma_dir),
            cfg.collection,
            cfg.k * FETCH_K_MULTIPLIER,
            settings.mmr_lambda,
        )
        svc = AssistantService(retriever, llm, corpus, cfg.k)
        jobs += [Job(cfg, svc, retriever, llm, q) for q in QUERIES]

    log.info("running %d answers, judged by %s", len(jobs), JUDGE_MODEL)
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda job: run_one(job, judge), jobs))
    summary = summarize(rows, configs)
    write_outputs(args.experiment, rows, summary)
    for s in summary:
        log.info("summary %s", s)


if __name__ == "__main__":
    main()
