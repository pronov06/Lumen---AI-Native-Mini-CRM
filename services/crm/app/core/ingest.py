"""Receipt ingestion — what happens to every callback the channel sends back.

The flow, per callback, inside one transaction:
  1. Append the event to the log, idempotently. Duplicate -> stop (no-op).
  2. Re-fold *all* of that communication's events into a fresh projection.
     (Folding the whole log, not patching the row, is what keeps out-of-order
     and duplicate events correct — the projection is always a function of the
     full set, never of arrival order.)
  3. Write the projection back onto the communication cache row.
  4. On a first-time `clicked`, attribute an order to the comm.
  5. Publish the new state to the live feed.

Step 2 re-reads the log each time, which is O(events-per-comm). For this scope
(~5 events/comm) that's trivial. At real scale you'd keep an incremental
projection or snapshot; I'm choosing clarity + provable correctness here and can
say exactly what I'd change under load.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.bus import Bus
from app.core.locks import KeyedLocks
from app.domain.lifecycle import CommState
from app.domain.projection import CommEvent, CommProjection
from app.infra.repo import Repo


class Ingestor:
    def __init__(self, repo: Repo, bus: Bus, locks: KeyedLocks | None = None):
        self.repo = repo
        self.bus = bus
        self.locks = locks

    async def ingest(
        self,
        *,
        communication_id: str,
        event_type: str,
        provider_event_id: str,
        occurred_at: datetime | None = None,
        meta: dict | None = None,
    ) -> dict:
        # Serialize the whole read-modify-write-commit per communication so a
        # concurrent ingest for the same comm can't clobber the cached projection
        # with a stale fold. Falls through unlocked when no manager is wired.
        if self.locks is not None:
            async with self.locks.lock(communication_id):
                return await self._ingest_locked(
                    communication_id=communication_id, event_type=event_type,
                    provider_event_id=provider_event_id,
                    occurred_at=occurred_at, meta=meta,
                )
        return await self._ingest_locked(
            communication_id=communication_id, event_type=event_type,
            provider_event_id=provider_event_id, occurred_at=occurred_at, meta=meta,
        )

    async def _ingest_locked(
        self,
        *,
        communication_id: str,
        event_type: str,
        provider_event_id: str,
        occurred_at: datetime | None = None,
        meta: dict | None = None,
    ) -> dict:
        # FOR UPDATE locks the row on Postgres so concurrent instances serialize
        # too; on SQLite it's ignored and the in-process lock above does the job.
        comm = await self.repo.get_communication_for_update(communication_id)
        if comm is None:
            await self.repo.s.rollback()
            return {"status": "unknown_communication", "communication_id": communication_id}

        state = CommState(event_type)  # raises ValueError on a bogus type -> 422
        now = datetime.now(timezone.utc)
        event = CommEvent(
            communication_id=communication_id,
            event_type=state,
            provider_event_id=provider_event_id,
            occurred_at=occurred_at or now,
            received_at=now,
            meta=meta or {},
        )

        inserted = await self.repo.append_event(event)
        if not inserted:
            # Idempotent replay — state is already settled, nothing to publish.
            await self.repo.s.commit()
            return {"status": "duplicate", "communication_id": communication_id,
                    "state": comm.state}

        # Re-derive the projection from the full event log.
        events = await self.repo.get_events(communication_id)
        proj = CommProjection.from_events(communication_id, events)

        was_not_clicked = comm.state != CommState.CLICKED.value
        await self.repo.write_projection(proj)

        # First-time click drives order attribution.
        if proj.state is CommState.CLICKED and was_not_clicked:
            await self.repo.attribute_order_on_click(comm)

        await self.repo.s.commit()

        update = {
            "type": "communication.updated",
            "communication_id": communication_id,
            "campaign_id": comm.campaign_id,
            "channel": comm.channel,
            "state": proj.state.value,
            "failed": proj.failed,
            "failure_reason": proj.failure_reason,
            "at": now.isoformat(),
        }
        await self.bus.publish_update(update)
        return {"status": "applied", **update}
