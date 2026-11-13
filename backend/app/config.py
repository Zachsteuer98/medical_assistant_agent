"""Runtime configuration, loaded from environment / repo-root .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.rag.routing import DEFAULT_ROUTING_CANDIDATES, DEFAULT_SECOND_DOCUMENT_RATIO

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    corpus: str = "merck"
    # Vector collection to serve; defaults to the corpus's collection (CorpusSpec).
    collection: str | None = None

    generator_model: str = "gpt-4o-mini"
    # 0.0 chosen from the parameter sweep: reproducible output matters most in clinical use.
    temperature: float = 0.0
    # Large enough that multi-step protocols are never truncated (a failure seen at 500).
    max_tokens: int = 1500
    top_k: int = 5
    fetch_k: int = 20
    mmr_lambda: float = 0.7
    # Guideline routing for multi-document corpora; single-document corpora (Merck) ignore it.
    # On by default: public eval correctness 3.77 -> 4.08 with refusals unchanged
    # (eval/summary_public_approach.md).
    route_by_document: bool = True
    routing_candidates: int = DEFAULT_ROUTING_CANDIDATES
    routing_second_document_ratio: float = DEFAULT_SECOND_DOCUMENT_RATIO
    # BM25 + dense rank fusion inside the routed guideline(s); needs routing, so it never
    # affects single-document corpora. On by default together with the public corpus's
    # recommendation-aware chunks: eval correctness 3.92 -> 4.38, refusals unchanged
    # (eval/summary_public_approach.md).
    hybrid_retrieval: bool = True
    llm_timeout_s: float = 30.0

    # Unset: each corpus uses its own store (see corpora.CorpusSpec.default_chroma_dir), so a
    # public-corpus index never shares a database file with licensed Merck-derived data.
    chroma_dir: Path | None = None
    allowed_origins: list[str] = ["http://localhost:5173"]
    rate_limit_per_minute: int = 10
    # Global cap on admitted /api/ask calls per UTC day, across all visitors (cost guard).
    daily_question_limit: int = Field(100, gt=0)
    # Number of reverse proxies in front of the API, each appending to X-Forwarded-For. The
    # client is taken that many entries from the right end; 0 means no proxy (use the socket
    # peer). Too low is safe (visitors share a bucket); too high would trust forgeable entries.
    trusted_proxy_hops: int = Field(1, ge=0)
    # Log the socket peer and X-Forwarded-For chain per ask, to verify trusted_proxy_hops.
    log_client_chain: bool = False
    # Built frontend to serve at / (optional). Unset or blank: API only.
    static_dir: Path | None = None
    # Extra comma-separated regexes for corpus-specific noise lines.
    watermark_patterns: str = ""

    @field_validator("static_dir", mode="before")
    @classmethod
    def _blank_static_dir_is_unset(cls, value: object) -> object:
        # An empty STATIC_DIR= line would otherwise parse as Path("."), serving the cwd.
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
