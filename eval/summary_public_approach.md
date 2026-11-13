# Experiment: public_approach

Mean scores (1-5) over answerable queries.

| config | context_relevance | groundedness | answer_relevance | page_cited_answers | correct_refusals | guideline_hit_rate | page_hit_rate | unwarranted_refusals | correctness | pass/partial/fail | mean_fact_coverage | mean_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Plain LLM | n/a | 3.23 | 4.08 | 0/13 | 0/3 | n/a | n/a | 0/13 | 2.23 | 2/4/7 | 0.55 | 4.7 |
| Prompt-engineered LLM | n/a | 2.46 | 3.69 | 0/13 | 0/3 | n/a | n/a | 0/13 | 2.08 | 2/3/8 | 0.54 | 7.6 |
| RAG (production) | 4.92 | 5 | 5 | 13/13 | 3/3 | 13/13 | 12/13 | 0/13 | 3.62 | 7/3/3 | 0.8 | 3.0 |

Corpus: 10 VA/DoD Clinical Practice Guidelines (`public`). These numbers are not directly comparable to the Merck results (summary_approach.md): different corpus, different query set, and narrower guideline-specific questions. Retrieval hit rates count RAG answers whose top-k context contains the expected guideline (guideline hit) or a chunk from that guideline's expected recommendation/discussion pages (page hit). Correctness is judged against 1-3 reference facts per question, without the retrieved context: pass = every fact fully stated and no contradiction; partial = some facts missing or incomplete, no contradiction; fail = a contradiction (conflicting advice, or conflicting advice imported from another guideline) or no fact covered. In means, pass = 5, partial = 3, fail = 1. Written analysis and manual review: [analysis_public.md](analysis_public.md).

## Per-query scores (context_relevance / groundedness / answer_relevance)

| query | Plain LLM | Prompt-engineered LLM | RAG (production) | RAG retrieval hit (guideline/page) |
|---|---|---|---|---|
| P01 Diabetes: glycemic target | –/3/4 | –/1/2 | 5/5/5 | yes/yes |
| P02 Diabetes: pharmacotherapy | –/5/5 | –/5/5 | 5/5/5 | yes/yes |
| P03 Hypertension: BP goal | –/4/5 | –/4/5 | 5/5/5 | yes/yes |
| P04 Hypertension: resistant HTN | –/3/3 | –/1/3 | 5/5/5 | yes/yes |
| P05 Lipids: primary prevention | –/2/3 | –/2/3 | 5/5/5 | yes/yes |
| P06 Lipids: statin intolerance | –/4/5 | –/4/5 | 5/5/5 | yes/yes |
| P07 Asthma: step-up therapy | –/4/5 | –/1/5 | 4/5/5 | yes/no |
| P08 COPD: initial maintenance therapy | –/3/4 | –/1/3 | 5/5/5 | yes/yes |
| P09 CKD: SGLT2 inhibitors | –/3/5 | –/2/4 | 5/5/5 | yes/yes |
| P10 Depression: continuation phase | –/4/5 | –/3/4 | 5/5/5 | yes/yes |
| P11 Low back pain: pharmacotherapy | –/1/2 | –/1/1 | 5/5/5 | yes/yes |
| P12 Headache: acute migraine | –/4/4 | –/4/4 | 5/5/5 | yes/yes |
| P13 Insomnia: first-line treatment | –/2/3 | –/3/4 | 5/5/5 | yes/yes |
| P14 Out of scope (near miss: COPD antibiotics) | –/1/5 | –/1/5 | 1/5/1 | – |
| P15 Out of scope (near miss: gout as side effect) | –/1/5 | –/1/5 | 1/5/1 | – |
| P16 Out of scope | –/1/5 | –/1/5 | 1/5/1 | – |

## Per-query correctness (grade, fact coverage; ! = contradiction)

| query | Plain LLM | Prompt-engineered LLM | RAG (production) |
|---|---|---|---|
| P01 Diabetes: glycemic target | partial 0.50 | fail 0.00 ! | pass 1.00 |
| P02 Diabetes: pharmacotherapy | pass 1.00 | pass 1.00 | pass 1.00 |
| P03 Hypertension: BP goal | pass 1.00 | pass 1.00 | pass 1.00 |
| P04 Hypertension: resistant HTN | fail 0.50 ! | fail 0.50 ! | pass 1.00 |
| P05 Lipids: primary prevention | fail 0.50 ! | fail 0.67 ! | pass 1.00 |
| P06 Lipids: statin intolerance | partial 0.33 | partial 0.33 | fail 0.67 ! |
| P07 Asthma: step-up therapy | fail 0.50 ! | fail 0.50 ! | fail 0.50 ! |
| P08 COPD: initial maintenance therapy | fail 0.50 ! | fail 0.50 ! | fail 0.00 ! |
| P09 CKD: SGLT2 inhibitors | fail 0.25 ! | fail 0.50 ! | partial 0.75 |
| P10 Depression: continuation phase | partial 0.50 | partial 0.50 | pass 1.00 |
| P11 Low back pain: pharmacotherapy | fail 0.50 ! | fail 0.50 ! | partial 0.67 |
| P12 Headache: acute migraine | partial 0.33 | partial 0.33 | pass 1.00 |
| P13 Insomnia: first-line treatment | fail 0.75 ! | fail 0.75 ! | partial 0.75 |
