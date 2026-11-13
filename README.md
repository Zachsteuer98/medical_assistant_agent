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
- [x] Evaluation harness: RAG-triad LLM-as-judge ([approach comparison](eval/summary_approach.md), [chunk-size results](eval/summary_chunk_size.md))
- [x] Frontend: React chat UI with citation panel
- [x] Tests, Docker, CI (privacy guard, lint, tests, image builds on every push)
- [x] Business findings deck ([PowerPoint](deck/Medical_Assistant_Agent_Findings.pptx))
- [ ] Demo GIF and screenshots in this README
- [x] Public demo corpus chosen: VA/DoD Clinical Practice Guidelines ([ADR 0004](docs/adr/0004-public-demo-corpus.md))
- [x] Public corpus: pinned download, multi-PDF ingest, guideline-named citations in the UI
- [ ] Public corpus eval run
- [ ] Deployment with rate limiting and a spend cap

## Business findings

📊 [Findings deck (PowerPoint)](deck/Medical_Assistant_Agent_Findings.pptx): problem, solution, evaluation results, risks and recommendations. Rebuild it from the eval summaries with `cd deck && npm install && npm run build`.

## Architecture

```
React (Vite, TS) ──/api/ask──▶ FastAPI ──▶ Chroma (MiniLM; guideline routing → BM25 + dense hybrid → MMR)
   citation chips  ◀── answer + citations ──┘      └──▶ gpt-4o-mini (temp 0)
```

Key decisions are recorded in [`docs/adr/`](docs/adr/).

## Run locally

Prerequisites: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22 and an OpenAI API key.
By default the app serves the **public corpus**: 10 VA/DoD Clinical Practice Guidelines that a
script downloads for you ([ADR 0004](docs/adr/0004-public-demo-corpus.md)).

```bash
cp .env.example .env                              # add OPENAI_API_KEY; CORPUS=public by default

cd backend
uv sync --all-groups
uv run python -m app.download --corpus public     # fetch the 10 pinned PDFs (hash-checked)
uv run python -m app.ingest --corpus public       # build the public_rec collection in data/chroma_public (~6 min on CPU)
CORPUS=public uv run uvicorn app.main:create_app --factory --port 8000

cd ../frontend                                    # in a second terminal
npm install
npm run dev                                       # http://localhost:5173
```

<details>
<summary>Merck corpus (local only, licensed copy required)</summary>

Place your own copy at `data/raw/merck.pdf` (not included, see [Data & licensing](#data--licensing)), then:

```bash
cd backend
uv run python -m app.ingest --corpus merck        # builds data/chroma (~15-20 min on CPU)
CORPUS=merck uv run uvicorn app.main:create_app --factory --port 8000
```
</details>

### Or with Docker

```bash
docker compose up --build                         # http://localhost:8080
```

The index must already exist on the host. Compose mounts `CHROMA_HOST_DIR` (default
`./data/chroma_public`). For Merck, set `CORPUS=merck` and `CHROMA_HOST_DIR=./data/chroma` in `.env`.

## Test

```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```

## Evaluate

```bash
cd backend && uv run python -m evaluation.run --experiment chunk_size   # ~$1-2 API cost (Merck query set)
```

## Data & licensing

The evaluated results use a personally licensed medical manual that is **not** included
in this repository. The live demo will use VA/DoD Clinical Practice Guidelines (U.S. government publications). See
[ADR 0001](docs/adr/0001-corpus-licensing.md) and [ADR 0004](docs/adr/0004-public-demo-corpus.md).

## Origin

Started as a capstone project for the UT Austin McCombs / Great Learning AI & ML program.

## License

MIT
