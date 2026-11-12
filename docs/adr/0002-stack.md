# ADR 0002 — Stack: FastAPI + React

**Context.** Portfolio project needs a real client/server split; RAG logic already exists in Python.

**Decision.** FastAPI backend (reuses notebook logic: PyMuPDF, Chroma, MiniLM embeddings,
OpenAI) and a React + Vite + TypeScript frontend. Docker Compose for local runs.

**Consequences.** More setup than Streamlit, but demonstrates API design, typed contracts,
and frontend skills. Streamlit rejected as prototype-grade.
