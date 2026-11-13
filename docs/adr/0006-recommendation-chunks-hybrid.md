# ADR 0006 — Recommendation-aware chunks and hybrid BM25 + dense retrieval

**Context.** After guideline routing (ADR 0005), the remaining public-corpus failures were
inside the right guideline (`eval/analysis_public.md`, run 3):
- COPD Rec 8 was glued, via chunk overlap, to the tail of the Rec 7 discussion and ranked far
  outside the candidate pool.
- CKD and low-back-pain recommendation-table chunks were near-duplicates of their neighbours,
  so MMR dropped them as redundant.

**Decision.** For the public corpus only (per-corpus settings in `corpora.py`; Merck unaffected):
1. **Recommendation-aware chunking** (`split_text_structured`):
   - A "Recommendation" heading plus its numbered statement is a hard boundary: it always
     starts a new chunk, with no overlap carried in.
   - Recommendation-table rows are soft boundaries: chunks break only between rows, and short
     rows are packed whole up to the 200-token target.
   - A line only counts as a recommendation if "we recommend", "we suggest" or "insufficient
     evidence" follows within 400 characters.
   - Over-long sections still split at 200 tokens with 40-token overlap.
2. **Hybrid retrieval inside the routed guideline(s):**
   - Every chunk of the routed guideline is scored by dense cosine and by BM25
     (hand-rolled, k1 = 1.2, b = 0.75; no new dependency).
   - The two rankings are fused with reciprocal rank fusion (constant 60, the published
     default, not tuned).
   - MMR then runs with the fused score as its relevance term; redundancy stays cosine.
3. The index is served from a new collection, `public_rec`, which `app.ingest --corpus public`
   now builds by default. On by default (`hybrid_retrieval`), and only possible together with
   routing.

Strict one-row-per-chunk splitting was tried and rejected: questions needing ~8 table rows
lost facts at k=5.

**Evidence** (`eval/summary_public_approach.md`, same run, 13 answerable + 3 out-of-scope):

| Config | Correctness (1–5) | Pass / partial / fail | Fact coverage | Refusals |
|---|---|---|---|---|
| Routing only (`public`) | 3.92 | 8 / 3 / 2 | 0.85 | 3/3 |
| **Rec chunks + hybrid (`public_rec`)** | **4.38** | **10 / 2 / 1** | **0.88** | 3/3 |

CKD (P09) and low-back-pain (P11) questions now pass; nothing that passed before fails.
Retrieval is about 150–200 ms per query.

**Consequences.**
- The serving process holds the public corpus's chunks and vectors in memory for BM25
  (~3,870 chunks, ~6 MB). Fine at this size; revisit for a much larger corpus.
- COPD Rec 8 (P08) still fails: isolating its table row removed "COPD" from the chunk text, so
  its dense rank fell. Candidate fix: prefix each chunk with its guideline/section name before
  embedding (re-ingest).
- The old `public` collection is no longer built by code; it is kept only as a frozen artifact
  for the eval comparison configs.
- Three rounds of changes have now been tuned on the same 13 questions. Further retrieval
  changes should be measured on new, held-out questions.
