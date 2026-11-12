# Experiment: approach

Mean scores (1-5) over answerable queries.

| config | context_relevance | groundedness | answer_relevance | page_cited_answers | correct_refusals | mean_latency_s |
|---|---|---|---|---|---|---|
| Plain LLM | n/a | 3.44 | 5 | 0/9 | 0/1 | 8.2 |
| Prompt-engineered LLM | n/a | 2.89 | 4.89 | 0/9 | 0/1 | 10.1 |
| RAG (production) | 4.22 | 4.89 | 4.89 | 9/9 | 1/1 | 3.5 |

## Per-query scores (context_relevance / groundedness / answer_relevance)

| query | Plain LLM | Prompt-engineered LLM | RAG (production) |
|---|---|---|---|
| Q1 Critical care | –/3/5 | –/2/5 | 4/5/5 |
| Q2 Diagnosis & surgery | –/5/5 | –/5/5 | 5/5/5 |
| Q3 Dermatology | –/4/5 | –/5/5 | 5/5/5 |
| Q4 Neurotrauma | –/3/5 | –/1/4 | 4/5/5 |
| Q5 Orthopedic trauma | –/3/5 | –/3/5 | 4/5/5 |
| Q6 Diagnostic assistance | –/5/5 | –/4/5 | 5/5/5 |
| Q7 Drug information | –/1/5 | –/1/5 | 3/4/4 |
| Q8 Treatment plans | –/3/5 | –/1/5 | 4/5/5 |
| Q9 Specialty knowledge | –/4/5 | –/4/5 | 4/5/5 |
| Q10 Out of scope (post-2011) | –/1/5 | –/1/5 | 1/5/1 |
