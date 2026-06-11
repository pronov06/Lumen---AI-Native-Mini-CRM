"""The message bus: a send queue (CRM -> worker) and a pub/sub channel
(projection updates -> WebSocket fan-out).

Two implementations behind one Protocol:
  - InProcessBus: asyncio primitives, single process. Zero infra — used for local
    dev and the whole test suite.
  - RedisBus: a Redis list as the durable send queue and Redis pub/sub for the
    live feed fan-out across instances. Used in docker-compose / production.

Keeping this behind a Protocol is what lets the integration test exercise the
*entire* loop without standing up Redis.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol


class Bus(Protocol):
    async def enqueue_send(self, payload: dict) -> None: ...
    async def dequeue_send(self) -> dict | None: ...
    async def publish_update(self, payload: dict) -> None: ...
    def subscribe_updates(self) -> AsyncIterator[dict]: ...


class InProcessBus:
    def __init__(self) -> None:
        self._send_q: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers: set[asyncio.Queue[dict]] = set()

    async def enqueue_send(self, payload: dict) -> None:
        await self._send_q.put(payload)

    async def dequeue_send(self) -> dict | None:
        return await self._send_q.get()

    async def publish_update(self, payload: dict) -> None:
        # Fan out to every live WebSocket subscriber. Slow subscribers drop
        # rather than block the loop (the feed is best-effort, the DB is truth).
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def subscribe_updates(self) -> AsyncIterator[dict]:  # type: ignore[override]
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)


class RedisBus:
    """Redis-backed bus. Imported lazily so the app runs without redis installed
    when CRM_BUS=memory."""

    SEND_KEY = "xeno:send_queue"
    UPDATES_CHANNEL = "xeno:updates"

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis  # local import: optional dependency

        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def enqueue_send(self, payload: dict) -> None:
        await self._redis.rpush(self.SEND_KEY, json.dumps(payload))

    async def dequeue_send(self) -> dict | None:
        item = await self._redis.blpop(self.SEND_KEY, timeout=5)
        return json.loads(item[1]) if item else None

    async def publish_update(self, payload: dict) -> None:
        await self._redis.publish(self.UPDATES_CHANNEL, json.dumps(payload))

    async def subscribe_updates(self) -> AsyncIterator[dict]:  # type: ignore[override]
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.UPDATES_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(self.UPDATES_CHANNEL)


def make_bus(kind: str, redis_url: str) -> Bus:
    return RedisBus(redis_url) if kind == "redis" else InProcessBus()
