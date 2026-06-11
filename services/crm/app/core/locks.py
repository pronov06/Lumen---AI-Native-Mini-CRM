"""Per-key async locks.

The communication cache row is a read-modify-write: append an event, re-fold the
whole log, write the projection back. Two of those running concurrently for the
*same* communication (e.g. the worker writing 'sent' while a 'delivered' callback
lands) can interleave and the later commit clobbers the earlier fold with a stale
state — a lost update. The event log stays correct, but the cached row goes
stale.

This serializes the critical section per communication_id within the process, so
same-comm ingests run one at a time. Different comms still run concurrently. For
a multi-instance deployment this pairs with a row-level SELECT ... FOR UPDATE on
the communication (a no-op on SQLite, a real lock on Postgres).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class KeyedLocks:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiters: dict[str, int] = {}

    @asynccontextmanager
    async def lock(self, key: str):
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            async with lock:
                yield
        finally:
            self._waiters[key] -= 1
            if self._waiters[key] == 0:
                # No one else is using this key's lock — drop it so the registry
                # doesn't grow without bound.
                self._waiters.pop(key, None)
                self._locks.pop(key, None)
