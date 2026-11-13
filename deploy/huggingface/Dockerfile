# syntax=docker/dockerfile:1
# Hugging Face Docker Space: one container serves the API and the built frontend on port 7860.
# Staged by deploy/huggingface/stage.py (build context = build/space).

FROM node:22.17.0-alpine AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM python:3.12.11-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

# Hugging Face runs Space containers as UID 1000.
RUN useradd --create-home --uid 1000 user
USER user

ENV HOME=/home/user \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/home/user/app/backend/.venv/bin:$PATH" \
    CORPUS=public \
    DAILY_QUESTION_LIMIT=100 \
    TRUSTED_PROXY_HOPS=1 \
    CHROMA_DIR=/home/user/app/index \
    STATIC_DIR=/home/user/app/static

WORKDIR /home/user/app/backend

# Dependencies first for layer caching; --frozen fails if uv.lock is stale.
COPY --chown=user backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY --chown=user backend/app ./app

# Bake the ONNX embedding model into the image so startup never downloads it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warmup'])"

# Prebuilt index of the public VA/DoD guidelines (ADR 0004/0007). Never the licensed Merck data.
COPY --chown=user index /home/user/app/index
COPY --chown=user --from=web /app/dist /home/user/app/static

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health', timeout=4)"

# --no-proxy-headers: the app derives the client IP itself from the proxy-appended end of
# X-Forwarded-For (TRUSTED_PROXY_HOPS); uvicorn's "*" trust would take the spoofable leftmost entry.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860", \
     "--no-proxy-headers"]
