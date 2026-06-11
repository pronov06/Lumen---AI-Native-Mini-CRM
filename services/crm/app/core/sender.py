"""The send worker — the CRM->channel half of the loop.

A campaign's `approve` enqueues one send payload per recipient; this worker
drains the queue off the request thread (so a 10k-recipient campaign doesn't
block an HTTP handler) and calls the channel service with retry + dead-letter.

Two things worth defending:
  - We never resolve delivery inline. The worker's job ends at "the channel
    accepted the send"; everything after that arrives asynchronously via
    /receipts. The synchronous return is only the *acknowledgement*.
  - Even our own "sent" is written as an event in the same append-only log the
    callbacks use, so there's exactly one path that changes a comm's state.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.bus import Bus
from app.core.channel_client import ChannelClient
from app.core.config import Settings
from app.core.ingest import Ingestor
from app.core.locks import KeyedLocks
from app.core.retry import RetryExhausted, with_retry
from app.infra.repo import Repo

log = logging.getLogger("crm.sender")


class Sender:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], bus: Bus,
                 channel: ChannelClient, settings: Settings,
                 locks: "KeyedLocks | None" = None):
        self.session_factory = session_factory
        self.bus = bus
        self.channel = channel
        self.settings = settings
        self.locks = locks
        self._stop = asyncio.Event()

    async def run_worker(self) -> None:
        log.info("send worker started")
        while not self._stop.is_set():
            try:
                payload = await self.bus.dequeue_send()
            except Exception as exc:  # noqa: BLE001 — keep the worker alive
                log.warning("dequeue error: %s", exc)
                await asyncio.sleep(0.2)
                continue
            if payload is None:
                continue
            await self._process(payload)

    def stop(self) -> None:
        self._stop.set()

    async def _process(self, payload: dict) -> None:
        comm_id = payload["communication_id"]
        try:
            await with_retry(
                lambda: self.channel.send(
                    communication_id=comm_id,
                    recipient=payload["recipient"],
                    message=payload["message"],
                    channel=payload["channel"],
                ),
                max_attempts=self.settings.retry_max_attempts,
                base_delay_ms=self.settings.retry_base_delay_ms,
                max_delay_ms=self.settings.retry_max_delay_ms,
            )
            await self._record(comm_id, "sent", "send-ack")
        except RetryExhausted as exc:
            log.error("send to channel failed for %s: %s", comm_id, exc)
            await self._dead_letter_and_fail(comm_id, payload, str(exc), exc.attempts)

    async def _record(self, comm_id: str, event_type: str, provider_event_id: str,
                      meta: dict | None = None) -> None:
        async with self.session_factory() as session:
            ingestor = Ingestor(Repo(session), self.bus, self.locks)
            await ingestor.ingest(communication_id=comm_id, event_type=event_type,
                                  provider_event_id=provider_event_id, meta=meta or {})

    async def _dead_letter_and_fail(self, comm_id: str, payload: dict, error: str,
                                    attempts: int) -> None:
        async with self.session_factory() as session:
            repo = Repo(session)
            await repo.record_dead_letter("send", payload, error, attempts)
            ingestor = Ingestor(repo, self.bus, self.locks)
            await ingestor.ingest(communication_id=comm_id, event_type="failed",
                                  provider_event_id="send-deadletter",
                                  meta={"reason": "channel_unreachable"})
