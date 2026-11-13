# ADR 0004 — Public demo corpus: VA/DoD Clinical Practice Guidelines

**Context.** ADR 0001 reserves a `public` corpus for the hosted demo but did not pick one.
The Merck Manual cannot be hosted (licence forbids sharing). Portfolio visitors use the demo
unsupervised and ask open-ended questions, so a single narrow-topic document (e.g. CDC STI
guidelines) would mostly answer "not in my sources" and look broken. StatPearls was
rejected: it is licensed CC BY-NC-ND, and the no-derivatives term makes chunking and
redisplaying its text ambiguous.

**Decision.** The `public` corpus is a bundle of full VA/DoD Clinical Practice Guidelines
(clinician-level PDFs from healthquality.va.gov):

| Topic | Path segment |
|---|---|
| Type 2 diabetes | `CD/diabetes` |
| Hypertension | `CD/htn` |
| Dyslipidemia | `CD/lipids` |
| Asthma (primary care) | `CD/asthma` |
| COPD | `CD/copd` |
| Chronic kidney disease | `CD/ckd` |
| Major depressive disorder | `MH/mdd` |
| Low back pain | `Pain/lbp` |
| Headache | `Pain/headache` |
| Insomnia / sleep apnea | `CD/insomnia` |

Suicide risk, substance use, and PTSD guidelines are deliberately excluded: an
unsupervised public chatbot should not be positioned as a source for crisis topics.

**Licensing evidence (checked 2026-11-12).** The 2023 diabetes CPG carries no copyright
notice or reproduction restriction; its suggested citation names the U.S. Government
Printing Office. It was drafted with contractor support (The Lewin Group, ECRI), so
copyright is not strictly guaranteed by 17 U.S.C. §105, but the guidelines are published
openly by VA/DoD and widely republished by other agencies (SAMHSA, AHRQ). Residual risk is
limited to embedded third-party figures; the demo displays only text excerpts with
attribution. Each PDF's front matter is re-checked at download time.

**Consequences.**
- Ingest must accept a directory of PDFs, and citations must name the source guideline
  as well as the page.
- PDFs and the vector store stay git-ignored like Merck; a download script fetches them.
- The UI shows the covered topics and example questions so visitors ask answerable questions.
- The eval harness is re-run on this corpus so the demo has its own published numbers;
  they are not directly comparable to the Merck results.
