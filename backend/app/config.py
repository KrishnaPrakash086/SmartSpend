from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# Single source of truth for ALL configuration — read from .env at startup, cached for the process lifetime
class AppSettings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://smartspend:smartspend@localhost:5432/smartspend"
    sync_database_url: str = "postgresql://smartspend:smartspend@localhost:5432/smartspend"

    # ── LLM provider switching — change one env var to swap providers without code changes
    llm_provider: Literal["gemini", "openrouter", "openai", "anthropic"] = "gemini"
    llm_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.0
    llm_request_timeout_seconds: int = 30
    llm_cooldown_seconds: int = 60

    # ── Provider-specific API keys ────────────────────────────────
    google_api_key: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # OpenRouter base URL — OpenRouter is OpenAI-compatible, so we route OpenAI client through it
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ── Voice / VAPI ──────────────────────────────────────────────
    vapi_secret: str = ""
    vapi_assistant_id: str = ""

    # ── Cache & queue ─────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── HTTP / CORS ───────────────────────────────────────────────
    cors_origins: str = "http://localhost:8080,http://localhost:5173,http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # ── Connection pool (SQLAlchemy) ──────────────────────────────
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 300

    # ── Observability ─────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def active_llm_api_key(self) -> str:
        # Returns the API key for whichever provider is currently selected
        provider_key_map = {
            "gemini": self.google_api_key,
            "openrouter": self.openrouter_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }
        return provider_key_map.get(self.llm_provider, "")


# lru_cache makes get_settings() effectively a singleton — first call builds, subsequent calls return cached instance
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
