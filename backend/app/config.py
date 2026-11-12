"""Runtime configuration, loaded from environment / repo-root .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    corpus: str = "merck"
    # Vector collection to serve; defaults to the corpus name.
    collection: str | None = None

    generator_model: str = "gpt-4o-mini"
    # 0.0 chosen from the parameter sweep: reproducible output matters most in clinical use.
    temperature: float = 0.0
    # Large enough that multi-step protocols are never truncated (a failure seen at 500).
    max_tokens: int = 1500
    top_k: int = 5
    fetch_k: int = 20
    mmr_lambda: float = 0.7
    llm_timeout_s: float = 30.0

    chroma_dir: Path = REPO_ROOT / "data" / "chroma"
    allowed_origins: list[str] = ["http://localhost:5173"]
    rate_limit_per_minute: int = 10
    # Extra comma-separated regexes for corpus-specific noise lines.
    watermark_patterns: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
