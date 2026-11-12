# Medical Assistant Agent

[![CI](https://github.com/Zachsteuer98/medical_assistant_agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Zachsteuer98/medical_assistant_agent/actions/workflows/ci.yml)

A retrieval-augmented (RAG) clinical decision-support assistant that answers medical
questions from trusted reference manuals and cites the exact source page for every claim.

> ⚠️ **Not medical advice.** Educational/portfolio project. Outputs are decision support
> only and must not replace evaluation by a licensed clinician.

## Status

🚧 In progress. Roadmap:

- [x] Prototype notebook (`notebooks/medical_assistant_rag.ipynb`)
- [x] Backend: FastAPI RAG service with page-level citations
- [x] Evaluation harness: RAG-triad LLM-as-judge ([chunk-size results](eval/summary_chunk_size.md))
- [x] Frontend: React chat UI with citation panel
- [x] Tests, Docker, CI (privacy guard, lint, tests, image builds on every push)
- [ ] Live demo (public-domain corpus)

## Business findings

📊 [Findings deck (PowerPoint)](deck/Medical_Assistant_Agent_Findings.pptx): problem, solution, evaluation results, risks and recommendations. Rebuild it from the eval summaries with `cd deck && npm install && npm run build`.

## Architecture

```
React (Vite, TS) ──/api/ask──▶ FastAPI ──▶ Chroma (MiniLM embeddings, MMR)
   citation chips  ◀── answer + citations ──┘      └──▶ gpt-4o-mini (temp 0)
```

Key decisions are recorded in [`docs/adr/`](docs/adr/).

## Run locally

Prerequisites: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22, an OpenAI API key,
and a corpus PDF at `data/raw/merck.pdf` (not included — see below).

```bash
cp .env.example .env                       # add OPENAI_API_KEY

cd backend
uv sync --all-groups
uv run python -m app.ingest --corpus merck # build the vector index (~15-20 min on CPU)
uv run uvicorn app.main:create_app --factory --port 8000

cd ../frontend                             # in a second terminal
npm install
npm run dev                                # http://localhost:5173
```

### Or with Docker

```bash
docker compose up --build                  # http://localhost:8080 (index must already exist in data/chroma)
```

## Test

```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```

## Evaluate

```bash
cd backend && uv run python -m evaluation.run --experiment chunk_size   # ~$1-2 API cost
```

## Data & licensing

The evaluated results use a personally licensed medical manual that is **not** included
in this repository. The live demo uses a public-domain corpus. See
[ADR 0001](docs/adr/0001-corpus-licensing.md).

## Origin

Started as a capstone project for the UT Austin McCombs / Great Learning AI & ML program.

## License

MIT
