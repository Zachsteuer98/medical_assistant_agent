# syntax=docker/dockerfile:1
FROM python:3.12.11-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    CHROMA_DIR=/data/chroma \
    HOME=/home/app \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Dependencies first for layer caching; --frozen fails if uv.lock is stale.
COPY pyproject.toml uv.lock ./
# --no-cache: no root-owned uv cache left in the app user's home.
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY app ./app

USER app
# Bake the ONNX embedding model into the image so startup never downloads it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warmup'])"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"

# The vector index is licensed-derived data: mounted at runtime, never baked in (ADR 0001).
# --no-proxy-headers: the app derives the per-client rate-limit key itself from the end of
# X-Forwarded-For that its own proxy appended (TRUSTED_PROXY_HOPS, default 1 = nginx in compose).
# uvicorn's --forwarded-allow-ips "*" would trust the spoofable leftmost entry instead.
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
