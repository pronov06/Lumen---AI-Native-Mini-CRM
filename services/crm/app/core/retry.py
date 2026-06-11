"""Retry with exponential backoff + full jitter.

Used for both directions of the loop (CRM->channel sends, channel->CRM
callbacks). Full jitter (random between 0 and the capped exponential delay)
avoids the thundering-herd where every retry fires in lockstep. After
`max_attempts` we give up and re-raise so the caller can dead-letter — we never
retry forever and never swallow the failure.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    def __init__(self, attempts: int, last_error: Exception):
        super().__init__(f"exhausted after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def _delay_seconds(attempt: int, base_ms: int, cap_ms: int) -> float:
    exp = min(cap_ms, base_ms * (2 ** attempt))
    return random.uniform(0, exp) / 1000.0  # full jitter


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay_ms: int = 100,
    max_delay_ms: int = 5_000,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    sleep=asyncio.sleep,
) -> T:
    last: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except retry_on as exc:  # noqa: PERF203
            last = exc
            if attempt + 1 >= max_attempts:
                break
            await sleep(_delay_seconds(attempt, base_delay_ms, max_delay_ms))
    raise RetryExhausted(max_attempts, last or Exception("unknown"))
