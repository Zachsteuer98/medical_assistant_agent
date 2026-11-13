"""FastAPI application: /api/health and /api/ask."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.corpora import CorpusSpec, get_corpus
from app.rag.llm import LLMError, OpenAIChatModel
from app.rag.routing import RoutingConfig
from app.rag.service import AssistantService
from app.rag.store import ChromaRetriever, IndexNotReadyError
from app.ratelimit import RateLimiter
from app.schemas import AskRequest, AskResponse, HealthResponse

logger = logging.getLogger("medical_assistant")


def routing_config(
    settings: Settings, corpus: CorpusSpec, enabled: bool | None = None
) -> RoutingConfig | None:
    """Routing for multi-document corpora; None (plain MMR) for single-document ones.

    enabled overrides settings.route_by_document (evaluation compares both).
    """
    on = settings.route_by_document if enabled is None else enabled
    if not on or not corpus.is_multi_document:
        return None
    return RoutingConfig(settings.routing_candidates, settings.routing_second_document_ratio)


def build_service(settings: Settings) -> AssistantService:
    corpus = get_corpus(settings.corpus)
    routing = routing_config(settings, corpus)
    retriever = ChromaRetriever(
        corpus.chroma_dir(settings.chroma_dir),
        settings.collection or corpus.default_collection,
        settings.fetch_k,
        settings.mmr_lambda,
        routing,
        hybrid=settings.hybrid_retrieval and routing is not None,
    )
    llm = OpenAIChatModel(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.generator_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout_s=settings.llm_timeout_s,
    )
    return AssistantService(retriever, llm, corpus, settings.top_k)


def create_app(
    service: AssistantService | None = None, settings: Settings | None = None
) -> FastAPI:
    settings = settings or get_settings()
    limiter = RateLimiter(settings.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service or build_service(settings)  # fail fast on bad config
        yield

    app = FastAPI(title="Medical Assistant Agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def get_service(request: Request) -> AssistantService:
        return request.app.state.service

    ServiceDep = Annotated[AssistantService, Depends(get_service)]

    def rate_limited(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(status_code=429, detail="Too many requests. Try again in a minute.")

    @app.get("/api/health", response_model=HealthResponse)
    def health(svc: ServiceDep) -> HealthResponse:
        return HealthResponse(
            status="ok", corpus=svc.corpus_name, indexed_chunks=svc.indexed_chunks()
        )

    @app.post("/api/ask", response_model=AskResponse, dependencies=[Depends(rate_limited)])
    def ask(body: AskRequest, svc: ServiceDep) -> AskResponse:
        started = time.perf_counter()
        try:
            result = svc.ask(body.question)
        except IndexNotReadyError as exc:
            raise HTTPException(status_code=503, detail="Knowledge base not ready.") from exc
        except LLMError as exc:
            logger.warning("ask_failed reason=%s", exc)
            raise HTTPException(
                status_code=502, detail="Language model unavailable. Please retry."
            ) from exc
        # Question text is not logged: it may contain patient information.
        logger.info(
            "ask_completed latency_ms=%d citations=%d answered=%s question_chars=%d",
            (time.perf_counter() - started) * 1000,
            len(result.citations),
            result.answered_from_context,
            len(body.question),
        )
        return result

    return app
