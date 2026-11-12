# ADR 0001 — Corpus licensing: dual corpus

**Context.** The original prototype used a personally licensed, watermarked copy of the
Merck Manual. Its licence forbids sharing; any vector store built from it is derived content.

**Decision.** Support two corpora behind one ingest interface:
- `merck` — local only, never committed or hosted. Used for the evaluation results in the deck.
- `public` — a public-domain medical corpus that powers the live hosted demo.

PDFs, vector stores, and eval CSVs containing retrieved text are git-ignored.

**Consequences.** Live demo answers differ from evaluated Merck answers; both are evaluated
with the same harness so results are comparable. Ingest must stay corpus-agnostic.
