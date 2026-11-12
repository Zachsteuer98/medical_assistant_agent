# Experiment: chunk_size

Mean scores (1-5) over answerable queries.

| config | context_relevance | groundedness | answer_relevance | correct_refusals | mean_latency_s |
|---|---|---|---|---|---|
| 1000-token chunks, k=5 (notebook baseline) | 3.89 | 5 | 4.33 | 1/1 | 10.0 |
| 200-token chunks, k=5 | 4.11 | 5 | 4.89 | 1/1 | 5.6 |
| 200-token chunks, k=25 (equal context budget) | 4.33 | 5 | 4.56 | 1/1 | 7.9 |

## Per-query scores (context_relevance / groundedness / answer_relevance)

| query | 1000-token chunks, k=5 (notebook baseline) | 200-token chunks, k=5 | 200-token chunks, k=25 (equal context budget) |
|---|---|---|---|
| Q1 Critical care | 4/5/5 | 4/5/5 | 5/5/5 |
| Q2 Diagnosis & surgery | 5/5/5 | 5/5/5 | 5/5/5 |
| Q3 Dermatology | 5/5/5 | 5/5/5 | 5/5/5 |
| Q4 Neurotrauma | 4/5/4 | 4/5/5 | 4/5/5 |
| Q5 Orthopedic trauma | 4/5/5 | 4/5/5 | 4/5/5 |
| Q6 Diagnostic assistance | 5/5/5 | 4/5/5 | 5/5/5 |
| Q7 Drug information | 1/5/1 | 3/5/4 | 2/5/1 |
| Q8 Treatment plans | 3/5/4 | 4/5/5 | 5/5/5 |
| Q9 Specialty knowledge | 4/5/5 | 4/5/5 | 4/5/5 |
| Q10 Out of scope (post-2011) | 1/5/1 | 1/5/1 | 1/5/1 |
