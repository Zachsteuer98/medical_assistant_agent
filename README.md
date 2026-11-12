# Medical Assistant Agent

A retrieval-augmented (RAG) clinical decision-support assistant that answers medical
questions from trusted reference manuals and cites the exact source page for every claim.

> ⚠️ **Not medical advice.** Educational/portfolio project. Outputs are decision support
> only and must not replace evaluation by a licensed clinician.

## Status

🚧 In progress. Roadmap:

- [x] Prototype notebook (`notebooks/medical_assistant_rag.ipynb`)
- [ ] Backend: FastAPI RAG service with citations
- [ ] Evaluation harness: baseline vs. prompt-engineered vs. RAG, LLM-as-judge
- [ ] Frontend: React chat UI with citation panel
- [ ] Tests, Docker, CI
- [ ] Live demo (public-domain corpus)

## Data & licensing

The evaluated results use a personally licensed medical manual that is **not** included
in this repository. The live demo uses a public-domain corpus. See
[ADR 0001](docs/adr/0001-corpus-licensing.md).

## Origin

Started as a capstone project for the UT Austin McCombs / Great Learning AI & ML program.

## License

MIT
