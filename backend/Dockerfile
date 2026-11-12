# syntax=docker/dockerfile:1
FROM python:3.12.11-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    CHROMA_DIR=/data/chroma \
    HOME=/home/app

RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Dependencies first for layer caching; --frozen fails if uv.lock is stale.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

USER app
# Bake the ONNX embedding model into the image so startup never downloads it.
RUN uv run --no-sync python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warmup'])"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD uv run --no-sync python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"

# The vector index is licensed-derived data: mounted at runtime, never baked in (ADR 0001).
# --proxy-headers: per-client rate limiting sees the real IP behind nginx. Trusting all
# forwarders is safe only because the API port is never published (compose uses `expose`).
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
