# Public corpus evaluation: analysis and manual review

Companion to [summary_public_approach.md](summary_public_approach.md). The harness never writes
this file; it is edited by hand.

## Setup

- Generator: gpt-4o-mini (temperature 0, production multi-document system prompt).
- Judges: gpt-4o (temperature 0) for the RAG triad and for answer correctness.
- Retrieval: k=5 MMR over 200-token chunks from 10 VA/DoD Clinical Practice Guidelines.
- Questions: 13 answerable plus 3 out-of-scope probes
  ([public_queries.py](../backend/evaluation/public_queries.py)).
- Single runs with n=13, so differences of a few tenths are noise.
- These numbers are **not directly comparable** to the Merck results
  ([summary_approach.md](summary_approach.md)): the corpus, the questions (narrow
  recommendation-level ones here, broad textbook topics there) and the out-of-scope probes all differ.

## Runs

| Run | Date | Adds | Approx. cost |
|---|---|---|---|
| 1 | 2026-11-12 | RAG triad, retrieval hit rate, refusals | $0.44 |
| 2 | 2026-11-12 | Answer correctness | $0.58 (+ $0.26 judge calibration on run-1 answers) |
| 3 | 2026-11-12 | Guideline routing as a 4th config ([ADR 0005](../docs/adr/0005-guideline-routing.md)) | ≤ $1.21 |

Costs are rebuilt from token counts at list prices, not billed figures. Temperature 0 is not
fully deterministic: 6 of 13 RAG answers were worded differently in run 2, but made the same
claims, so the manual verdicts still apply.

## Retrieval and refusals (same in both runs)

- The expected guideline was in the top 5 for 13/13 questions; a chunk from the expected pages
  for 12/13. The miss was P07, which got a neighbouring page on the same inhaler strategy.
  A page hit does not mean the chunk states the recommendation (see P08).
- RAG refused 3/3 out-of-scope questions, including near misses on pneumonia (COPD text
  retrieved) and gout (lipid text retrieved). Both baselines refused 0/3. RAG never refused an
  answerable question.

## Why a correctness metric

In both runs RAG groundedness and answer relevance were 5.00 on every question, because the
triad only compares the answer with the retrieved text. Manual review found:

- **P08 is wrong.** The answer recommends triple therapy taken from exacerbation guidance; the
  COPD guideline's Rec 8 recommends LABA/LAMA dual therapy for significant symptom burden.
- **P07 is misleading.** It misses ICS-formoterol as both controller and reliever (asthma Rec 7)
  and adds a "do not use maintenance inhalers for relief" warning from the COPD guideline that
  conflicts with that advice — text leaking across guidelines.
- **P09 and P11 are incomplete.** P09 leaves out the albuminuria and heart-failure indications;
  P11 leaves out NSAIDs and the advice against opioids and benzodiazepines.

## Correctness rubric

Implemented in [judge.py](../backend/evaluation/judge.py).

- The judge sees the question, 1–3 expected facts, the expected guideline's name and the answer.
  It never sees the retrieved context.
- **Per fact:** `yes` if every essential element is present (drug, threshold, population,
  direction); naming a drug class covers the listed drugs in that class. Otherwise `partly` or `no`.
- **Contradiction flag:** only for an explicit statement that would change management — a
  different drug, regimen, target or population for the same situation, a reversed for/against,
  or conflicting advice imported from another guideline. The judge must quote the sentence
  verbatim. Omissions are never contradictions.
- **Coverage** = (yes + 0.5 × partly) / number of facts.
- **Grade:** fail if there is a contradiction or coverage is 0; pass if every fact is `yes`;
  otherwise partial. In means, pass = 5, partial = 3, fail = 1.
- Malformed judge output raises `JudgeOutputError` rather than being scored.

## Calibration

The rubric was revised twice on the run-1 answers; the expected facts were not changed.

1. The first draft treated omissions as contradictions, turning P06, P09 and P11 into fails.
   Requiring a verbatim quote and ruling out omissions fixed that.
2. A general class-membership rule was added. It did not change P13; tuning stopped there rather
   than overfitting 13 items with nothing held out.

## Per-query correctness (RAG)

| Query | Manual verdict | Judge, run-1 answers | Judge, run 2 |
|---|---|---|---|
| P01 | pass | pass | pass |
| P02 | pass | pass | pass |
| P03 | pass | pass | pass |
| P04 | pass | pass | pass |
| P05 | pass | pass | pass |
| P06 | pass → partial (revised) | partial | fail (false contradiction) |
| P07 | fail | fail — quoted the COPD warning | fail |
| P08 | fail | fail — quoted the triple-therapy advice | fail |
| P09 | partial | partial | partial |
| P10 | pass | pass | pass |
| P11 | partial | partial | partial |
| P12 | pass | pass | pass |
| P13 | pass | partial | partial |

**Agreement:** 11/13 against the original manual verdicts in both runs; 12/13 on run-1 answers
against the revised P06 verdict.

- **P06:** the answer omits Rec 19 (switch to a non-statin if a statin is still not tolerated),
  which was in the expected pages, so the manual "pass" was too lenient. In run 2 the judge
  wrongly flagged "No specific contraindications or safety warnings are mentioned…" as a
  contradiction — a judge error.
- **P13:** the answer names drug classes, not individual drugs; the judge wanted the drugs.
  Stricter than the manual review, but defensible.
- Every disagreement leans strict: the judge did not pass any wrong answer.

## Results (run 2)

| Approach | Groundedness | Answer rel. | Correctness (1–5) | Pass / partial / fail | Fact coverage |
|---|---|---|---|---|---|
| Plain LLM | 3.23 | 4.08 | 2.23 | 2 / 4 / 7 | 0.55 |
| Prompt-engineered LLM | 2.46 | 3.69 | 2.08 | 2 / 3 / 8 | 0.54 |
| RAG (production) | 5.00 | 5.00 | 3.62 | 7 / 3 / 3 | 0.80 |

RAG context relevance was 4.92. The baselines fail mostly on genuine conflicts with VA/DoD
recommendations, e.g. HbA1c <7% instead of the 7.0–8.5% range, an ARB or beta-blocker instead
of spironolactone/amiloride, or suggesting acetaminophen or benzodiazepines where the
guidelines advise against them.

## Run 3: guideline routing

Routing scores each guideline over the top 20 candidates and runs MMR only within the top
guideline (plus the runner-up if it scores ≥ 0.5 × the top). See
[ADR 0005](../docs/adr/0005-guideline-routing.md).

| Config | Correctness (1–5) | Pass / partial / fail | Fact coverage | Page hit | Refusals |
|---|---|---|---|---|---|
| RAG, no routing | 3.77 | 7 / 4 / 2 | 0.80 | 12/13 | 3/3 |
| RAG, guideline routing (production) | 4.08 | 8 / 4 / 1 | 0.85 | 13/13 | 3/3 |

- The unrouted score moved from 3.62 (run 2) to 3.77 only because the P06 false contradiction
  did not recur — judge noise.
- Per query, routing changed only **P07** (fail → pass; the COPD warning no longer leaks in) and
  **P11** (coverage 0.67 → 0.83; opioids, benzodiazepines and corticosteroids now covered,
  NSAIDs still missing). Nothing that passed now fails.
- Retrieval got faster (664 → 350 ms per query) because the question is embedded once.
- Small effect on n=13 in one run: one question flipped, one improved.

Remaining failures, diagnosed without an LLM:

- **P08 (COPD) — chunking.** The Rec 8 discussion statement shares a chunk with the tail of the
  Rec 7 discussion and ranks #225 within COPD; the clean recommendation-table chunk ranks #23,
  outside the candidate pool. The exacerbation sidebar ranks #1 and drives the wrong answer.
  A quick BM25 test ranks the Rec 8 chunk #1.
- **P09 (CKD) and P11 (low back pain) — MMR redundancy.** The needed recommendation-table chunks
  rank in the top 4–7 but are dropped as near-duplicates of an adjacent chunk at λ=0.7.

## Follow-ups

- **Retrieval:** ~~same-guideline filtering~~ done in run 3. Next: chunk boundaries aligned to
  "Recommendation N." headings (P08, P09, P11), optionally with lexical (BM25) retrieval
  inside the routed guideline.
- **Judge:** build a larger labelled set with held-out questions before changing the rubric
  again, and add a check that a quoted contradiction really conflicts with a specific expected
  fact (would catch the P06 run-2 error).
