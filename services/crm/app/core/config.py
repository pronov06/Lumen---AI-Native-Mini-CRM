"""Runtime configuration. Everything secret or environment-specific comes from
the environment — no keys are hardcoded. `.env.example` documents every knob.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRM_", env_file=".env", extra="ignore")

    # Storage. Default is a local SQLite file so the app boots with zero infra;
    # docker-compose overrides this with the async Postgres URL.
    database_url: str = "sqlite+aiosqlite:///./crm.db"

    # Message bus. "memory" runs in-process (single instance, dev/test);
    # "redis" uses Redis for the send queue + pub/sub fan-out to WebSockets.
    bus: str = "memory"
    redis_url: str = "redis://localhost:6379/0"

    # The channel service the CRM calls on send.
    channel_base_url: str = "http://localhost:8001"

    # Where the channel service should POST callbacks back to (this CRM).
    # In docker-compose this is the CRM's service URL; locally it's localhost.
    crm_public_url: str = "http://localhost:8000"

    # Shared secret used to HMAC-sign callbacks so /receipts can't be spoofed.
    # MUST be overridden in any non-local environment.
    callback_secret: str = "dev-only-insecure-change-me"

    # AI co-pilot. With no key set, the co-pilot falls back to a deterministic
    # local planner so the product is fully usable offline / in CI.
    openrouter_api_key: str | None = None
    openrouter_model: str = "deepseek/deepseek-chat"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Gemini AI co-pilot. If configured, it will be preferred over OpenRouter.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Retry/backoff for outbound calls (send + callbacks share this policy).
    retry_max_attempts: int = 5
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 5_000

    # Comma-separated list of allowed CORS origins. Kept as a raw string because
    # pydantic-settings would otherwise try to JSON-parse a list-typed env var,
    # which rejects a plain comma-separated value. Use `cors_origins_list`.
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
