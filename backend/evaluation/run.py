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

from openai import OpenAI

from app.config import REPO_ROOT, get_settings
from app.corpora import get_corpus
from app.rag.llm import OpenAIChatModel
from app.rag.prompts import format_context
from app.rag.service import AssistantService
from app.rag.store import ChromaRetriever
from evaluation.judge import METRICS, Judge
from evaluation.queries import QUERIES, EvalQuery

JUDGE_MODEL = "gpt-4o"
WORKERS = 4
FETCH_K_MULTIPLIER = 4  # MMR candidate pool size relative to k
EVAL_DIR = REPO_ROOT / "eval"
log = logging.getLogger("eval")


@dataclass(frozen=True)
class RunConfig:
    name: str
    collection: str
    chunk_tokens: int
    k: int


EXPERIMENTS: dict[str, tuple[RunConfig, ...]] = {
    "chunk_size": (
        RunConfig("1000-token chunks, k=5 (notebook baseline)", "merck_c1000", 1000, 5),
        RunConfig("200-token chunks, k=5", "merck", 200, 5),
        RunConfig("200-token chunks, k=25 (equal context budget)", "merck", 200, 25),
    ),
}


def run_one(cfg: RunConfig, svc: AssistantService, judge: Judge, q: EvalQuery) -> dict:
    started = time.perf_counter()
    response, chunks = svc.ask_with_context(q.question)
    latency_s = time.perf_counter() - started
    context = format_context([(c.page, c.text) for c in chunks])
    row = {
        "config": cfg.name,
        "query_id": q.id,
        "category": q.category,
        "answerable": q.answerable,
        "question": q.question,
        "answered_from_context": response.answered_from_context,
        "retrieved_pages": " ".join(str(c.page) for c in chunks),
        "context_tokens_approx": len(context) // 4,
        "latency_s": round(latency_s, 2),
        "answer": response.answer,
        "context": context,
    }
    for metric in METRICS:
        verdict = judge.rate(metric, q.question, context, response.answer)
        row[metric] = verdict.score
        row[f"{metric}_rationale"] = verdict.rationale
    log.info("done config=%r query=%s %s", cfg.name, q.id, {m: row[m] for m in METRICS})
    return row


def summarize(rows: list[dict], configs: tuple[RunConfig, ...]) -> list[dict]:
    summary = []
    for cfg in configs:
        cfg_rows = [r for r in rows if r["config"] == cfg.name]
        answerable = [r for r in cfg_rows if r["answerable"]]
        out_of_scope = [r for r in cfg_rows if not r["answerable"]]
        entry = {"config": cfg.name}
        for metric in METRICS:
            entry[metric] = round(statistics.mean(r[metric] for r in answerable), 2)
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
            cells.append("/".join(str(r[m]) for m in METRICS))
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
        bars = ax.bar(xs, [s[m] for m in METRICS], width, label=s["config"])
        ax.bar_label(bars, fmt="%.2f", fontsize=8)
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
            settings.chroma_dir, cfg.collection, cfg.k * FETCH_K_MULTIPLIER, settings.mmr_lambda
        )
        svc = AssistantService(retriever, llm, corpus, cfg.k)
        jobs += [(cfg, svc, q) for q in QUERIES]

    log.info("running %d answers x %d judge metrics with %s", len(jobs), len(METRICS), JUDGE_MODEL)
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda job: run_one(job[0], job[1], judge, job[2]), jobs))
    summary = summarize(rows, configs)
    write_outputs(args.experiment, rows, summary)
    for s in summary:
        log.info("summary %s", s)


if __name__ == "__main__":
    main()
