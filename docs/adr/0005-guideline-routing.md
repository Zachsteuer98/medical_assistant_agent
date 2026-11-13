# ADR 0005 — Guideline routing for multi-document corpora

**Context.** The public corpus holds 10 separate VA/DoD guidelines (ADR 0004). MMR over the
whole corpus let near-topic chunks from another guideline take context slots: an asthma
question retrieved COPD text and the answer imported a COPD warning that contradicts asthma
advice. The RAG-triad judge scored that answer 5/5; only the correctness judge caught it
(`eval/analysis_public.md`).

**Decision.** For multi-document corpora, route each question before MMR
(`backend/app/rag/routing.py`):
1. Take the top 20 candidate chunks across the corpus.
2. Score each guideline by the summed similarity of its chunks among them.
3. Keep the top guideline, plus the runner-up if it scores ≥ 0.5 × the top (max 2), for
   questions that legitimately span two guidelines (e.g. CKD + diabetes).
4. Run the usual MMR (k=5, λ=0.7) only within the routed guideline(s).

On by default (`route_by_document`); constants are settings. Single-document corpora (Merck)
skip routing entirely and retrieve exactly as before.

**Evidence** (`eval/summary_public_approach.md`, 13 answerable + 3 out-of-scope questions, one run):

| Config | Correctness (1–5) | Pass / partial / fail | Page hit | Refusals | Retrieval |
|---|---|---|---|---|---|
| No routing | 3.77 | 7 / 4 / 2 | 12/13 | 3/3 | 664 ms |
| **Routing** | **4.08** | **8 / 4 / 1** | **13/13** | 3/3 | **350 ms** |

Cross-guideline chunks in the top 5 fell from 11 to 6, and all remaining ones are on the two
genuinely two-guideline questions.

**Consequences.**
- Fixes cross-guideline leakage; does not fix within-guideline misses (COPD Rec 8 is buried by
  chunking; near-duplicate table chunks are dropped by MMR). Those need recommendation-aware
  chunking.
- The 0.5 ratio sits in the observed gap (two-guideline questions ≈ 0.97, leakage ≈ 0.32) but
  depends on the candidate pool: at 40 candidates the leak rises to 0.58. Changing
  `routing_candidates` requires re-checking the ratio.
- A question spanning three or more guidelines loses the rest. Accepted for this corpus.
- Tuned on 13 questions with nothing held out; results are directional. Re-check when the
  query set grows.
