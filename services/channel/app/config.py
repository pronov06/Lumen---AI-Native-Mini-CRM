"""Channel service configuration.

The channel service is a *separate* service with its own config. It shares only
two things with the CRM by contract: the callback secret (to sign receipts) and
the lifecycle vocabulary. Everything about *how* it simulates lives here and is
tunable from the CRM settings panel via these env vars.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHANNEL_", env_file=".env", extra="ignore")

    # Outcome probabilities (per send). delivered -> opened -> read -> clicked
    # each gated by its own conditional probability, so the funnel narrows.
    failure_rate: float = 0.05      # P(hard fail instead of delivered)
    open_rate: float = 0.55         # P(open | delivered)
    read_rate: float = 0.70         # P(read | opened)
    click_rate: float = 0.30        # P(click | read)

    # Realism injectors — these make the loop earn its correctness guarantees.
    out_of_order_rate: float = 0.20  # P(shuffle a comm's callbacks before send)
    duplicate_rate: float = 0.08     # P(send a given callback twice)

    # Latency simulation (ms) between lifecycle stages.
    min_latency_ms: int = 50
    max_latency_ms: int = 600

    # Shared secret used to HMAC-sign callbacks. Must match the CRM's.
    callback_secret: str = "dev-only-insecure-change-me"

    # Retry policy for callback delivery (channel -> CRM).
    retry_max_attempts: int = 5
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 5_000

    # Optional fixed seed for deterministic simulation (tests set this).
    seed: int | None = None


@lru_cache
def get_channel_settings() -> ChannelSettings:
    return ChannelSettings()
