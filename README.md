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

## Deploy (Hugging Face Spaces)

Design and costs: [ADR 0007](docs/adr/0007-hosting-huggingface-spaces.md). You need a Hugging
Face account with a PRO plan (Docker Spaces require a paid plan), a write token, and a
**separate OpenAI key with a monthly limit** used only by the Space.

```bash
# 1. Build the bundle in build/space, including a fresh public index (~10 min on CPU)
cd backend && uv run python ../deploy/huggingface/stage.py --build-index && cd ..

# 2. Create the Space (public) and upload the bundle; add --dry-run to preview
HF_TOKEN=... uv run --no-project --with huggingface_hub==2.3.0 \
  python deploy/huggingface/publish.py --repo YOUR_USER/medical-assistant-agent
```

Then, in the Space settings:
- **Secrets:** `OPENAI_API_KEY` (the dedicated, capped key).
- **Variables (optional):** `DAILY_QUESTION_LIMIT` (default 100 questions per UTC day, all
  visitors), `TRUSTED_PROXY_HOPS` (default 1), `LOG_CLIENT_CHAIN=true` for the check below.
- **Hardware:** the free CPU tier sleeps after 48 hours without visitors; choose an upgraded
  hardware tier to keep it always on.

After the first deploy, verify the proxy hop count: with `LOG_CLIENT_CHAIN=true`, send one
question and read the `client_chain peer=... xff=[...] resolved=...` log line. `resolved` must be
your real public IP (compare `curl ifconfig.me`), and a request with a forged
`X-Forwarded-For: 1.2.3.4` header must still resolve to your real IP. If it resolves to a
Hugging Face address, raise `TRUSTED_PROXY_HOPS`; if it shows the forged value, lower it. Then
set `LOG_CLIENT_CHAIN` back to false (it logs visitor IPs).

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
