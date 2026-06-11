"""Repository — the only module that talks SQL. Everything above it deals in
domain objects, not rows. Idempotent event insert lives here because the
uniqueness guarantee is a database concern.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lifecycle import CommState
from app.domain.projection import CommEvent, CommProjection
from app.infra import models


class Repo:
    def __init__(self, session: AsyncSession):
        self.s = session

    # --- reset (idempotent re-seed) -----------------------------------------
    async def reset_all(self) -> None:
        """Wipe all demo data so re-seeding is deterministic. Order respects FKs:
        events/dead-letters/comms/orders/campaigns/customers."""
        for model in (
            models.CommunicationEvent,
            models.DeadLetter,
            models.Communication,
            models.Order,
            models.Campaign,
            models.Customer,
        ):
            await self.s.execute(delete(model))
        await self.s.flush()

    # --- customers / orders --------------------------------------------------
    async def upsert_customers(self, rows: list[dict]) -> int:
        for r in rows:
            self.s.add(models.Customer(**r))
        await self.s.flush()
        return len(rows)

    async def add_orders(self, rows: list[dict]) -> int:
        for r in rows:
            self.s.add(models.Order(**r))
        await self.s.flush()
        return len(rows)

    async def list_customers(self) -> list[models.Customer]:
        res = await self.s.execute(select(models.Customer))
        return list(res.scalars().all())

    async def count_customers(self) -> int:
        res = await self.s.execute(select(func.count(models.Customer.id)))
        return int(res.scalar_one())

    # --- campaigns -----------------------------------------------------------
    async def create_campaign(self, campaign: models.Campaign) -> models.Campaign:
        self.s.add(campaign)
        await self.s.flush()
        return campaign

    async def get_campaign(self, campaign_id: str) -> models.Campaign | None:
        return await self.s.get(models.Campaign, campaign_id)

    async def list_campaigns(self) -> list[models.Campaign]:
        res = await self.s.execute(
            select(models.Campaign).order_by(models.Campaign.created_at.desc())
        )
        return list(res.scalars().all())

    async def set_campaign_status(self, campaign_id: str, status: str,
                                  sent_at: datetime | None = None) -> None:
        values: dict = {"status": status}
        if sent_at:
            values["sent_at"] = sent_at
        await self.s.execute(
            update(models.Campaign).where(models.Campaign.id == campaign_id).values(**values)
        )

    # --- communications ------------------------------------------------------
    async def create_communications(self, rows: list[models.Communication]) -> None:
        self.s.add_all(rows)
        await self.s.flush()

    async def get_communication(self, comm_id: str) -> models.Communication | None:
        return await self.s.get(models.Communication, comm_id)

    async def get_communication_for_update(
        self, comm_id: str
    ) -> models.Communication | None:
        """Like get_communication but takes a row lock (SELECT ... FOR UPDATE) so
        concurrent ingests for the same comm serialize on Postgres. On SQLite the
        FOR UPDATE is ignored — the in-process KeyedLocks covers that case."""
        res = await self.s.execute(
            select(models.Communication)
            .where(models.Communication.id == comm_id)
            .with_for_update()
        )
        return res.scalars().first()

    async def list_communications(self, campaign_id: str) -> list[models.Communication]:
        res = await self.s.execute(
            select(models.Communication).where(
                models.Communication.campaign_id == campaign_id
            )
        )
        return list(res.scalars().all())

    # --- the append-only event log ------------------------------------------
    async def append_event(self, event: CommEvent) -> bool:
        """Insert one event. Returns True if newly inserted, False if it was a
        duplicate (idempotency: the unique constraint rejects the replay)."""
        row = models.CommunicationEvent(
            communication_id=event.communication_id,
            event_type=event.event_type.value,
            provider_event_id=event.provider_event_id,
            occurred_at=event.occurred_at,
            received_at=event.received_at,
            meta=event.meta,
        )
        # Insert inside a SAVEPOINT: a duplicate rolls back only the savepoint,
        # never the outer transaction, and never expires the already-loaded comm
        # row. A full session.rollback() here caused the loaded comm to be
        # expired and lazily reloaded — which could attempt IO outside the async
        # greenlet under concurrent callbacks (MissingGreenlet / spurious 500s).
        try:
            async with self.s.begin_nested():
                self.s.add(row)
                await self.s.flush()
            return True
        except IntegrityError:
            return False

    async def get_events(self, comm_id: str) -> list[CommEvent]:
        res = await self.s.execute(
            select(models.CommunicationEvent).where(
                models.CommunicationEvent.communication_id == comm_id
            )
        )
        return [
            CommEvent(
                communication_id=r.communication_id,
                event_type=CommState(r.event_type),
                provider_event_id=r.provider_event_id,
                occurred_at=r.occurred_at,
                received_at=r.received_at,
                meta=r.meta or {},
            )
            for r in res.scalars().all()
        ]

    async def write_projection(self, proj: CommProjection) -> None:
        """Persist the derived projection back onto the communication cache row."""
        ts = proj.state_timestamps
        await self.s.execute(
            update(models.Communication)
            .where(models.Communication.id == proj.communication_id)
            .values(
                state=proj.state.value,
                failed=proj.failed,
                failure_reason=proj.failure_reason,
                sent_at=ts.get(CommState.SENT),
                delivered_at=ts.get(CommState.DELIVERED),
                opened_at=ts.get(CommState.OPENED),
                read_at=ts.get(CommState.READ),
                clicked_at=ts.get(CommState.CLICKED),
                updated_at=proj.last_event_at,
            )
        )

    # --- attribution & dead letters -----------------------------------------
    async def attribute_order_on_click(self, comm: models.Communication) -> None:
        """When a comm is clicked, attribute the customer's next order (within a
        window) to it — this is what powers 'orders that came from this comm'."""
        # Simple, defensible attribution: the customer's most recent un-attributed
        # order after the click gets credited to this communication.
        res = await self.s.execute(
            select(models.Order)
            .where(
                models.Order.customer_id == comm.customer_id,
                models.Order.attributed_communication_id.is_(None),
            )
            .order_by(models.Order.placed_at.desc())
            .limit(1)
        )
        order = res.scalars().first()
        if order is not None:
            order.attributed_communication_id = comm.id
            await self.s.flush()

    async def attributed_order_count(self, campaign_id: str) -> int:
        res = await self.s.execute(
            select(func.count(models.Order.id))
            .select_from(models.Order)
            .join(
                models.Communication,
                models.Communication.id == models.Order.attributed_communication_id,
            )
            .where(models.Communication.campaign_id == campaign_id)
        )
        return int(res.scalar_one())

    def _projection_from_row(self, c: models.Communication) -> CommProjection:
        """Rebuild a CommProjection from the cached comm row (its denormalized
        lifecycle timestamps) — used for fast campaign stats without re-reading
        every event."""
        ts: dict = {}
        for state, val in (
            (CommState.SENT, c.sent_at), (CommState.DELIVERED, c.delivered_at),
            (CommState.OPENED, c.opened_at), (CommState.READ, c.read_at),
            (CommState.CLICKED, c.clicked_at),
        ):
            if val is not None:
                ts[state] = val
        return CommProjection(
            communication_id=c.id, state=CommState(c.state), state_timestamps=ts,
            failed=c.failed, failure_reason=c.failure_reason,
        )

    async def campaign_projections(self, campaign_id: str) -> list[CommProjection]:
        comms = await self.list_communications(campaign_id)
        return [self._projection_from_row(c) for c in comms]

    async def record_dead_letter(self, kind: str, payload: dict, error: str,
                                 attempts: int) -> None:
        self.s.add(models.DeadLetter(kind=kind, payload=payload, error=error,
                                     attempts=attempts))
        await self.s.flush()

    async def list_dead_letters(self) -> list[models.DeadLetter]:
        res = await self.s.execute(
            select(models.DeadLetter).order_by(models.DeadLetter.created_at.desc())
        )
        return list(res.scalars().all())
