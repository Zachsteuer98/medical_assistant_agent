# ADR 0003 — Chunk size: 200 tokens, k=5

**Context.** The notebook used 1000-token chunks, but the embedding model (all-MiniLM-L6-v2)
truncates input at 256 wordpieces, so ~75% of each chunk never influenced retrieval.

**Decision.** 200-token chunks with 40-token overlap; retrieve k=5 via MMR.

**Evidence** (`eval/summary_chunk_size.md`, 9 answerable queries, gpt-4o judge):

| Config | Context rel. | Answer rel. | Cited answers | Latency |
|---|---|---|---|---|
| 1000 tok, k=5 | 3.89 | 4.33 | 6/8 | 10.0 s |
| 200 tok, k=5 | 4.11 | **4.89** | **9/9** | **5.6 s** |
| 200 tok, k=25 | 4.33 | 4.56 | 6/8 | 7.9 s |

**Consequences.** ~4.6× more chunks (19,602) and a ~17 min index build; ~70% fewer prompt
tokens per question. Small sample — results are directional; re-run when the query set grows.
