"""Events and the projection that derives a communication's state from them.

The system is event-sourced-*lite*: callbacks are never applied as destructive
UPDATEs. Each one is appended to an immutable log as a `CommEvent`, and the
communication's current state is *computed* by folding that log. This is what
makes the loop honest — every stat traces back to a concrete event, and the same
log replays to the same state no matter what order it arrives in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .lifecycle import CommState, can_advance, rank


@dataclass(frozen=True, slots=True)
class CommEvent:
    """One immutable fact reported about one communication.

    idempotency_key is the dedup identity. The channel service is at-least-once,
    so the same logical event can arrive multiple times; ingesting a key we've
    already seen must be a no-op. We build it from
    `communication_id:event_type:provider_event_id` so a genuine retry collapses
    but two *distinct* opens (key differs by provider_event_id) both count.
    """

    communication_id: str
    event_type: CommState
    provider_event_id: str
    occurred_at: datetime          # when it happened at the channel (event time)
    received_at: datetime          # when the CRM ingested it (processing time)
    meta: dict = field(default_factory=dict)

    @property
    def idempotency_key(self) -> str:
        return f"{self.communication_id}:{self.event_type.value}:{self.provider_event_id}"


@dataclass(slots=True)
class CommProjection:
    """The derived current view of a communication, produced by folding events.

    `state_timestamps` keeps the first-seen time of every lifecycle state we
    observed, even ones we 'skipped' on the way forward — so an out-of-order
    `delivered` that lands after we already advanced to `read` still records
    *when* delivery happened, without moving the headline state backwards.
    """

    communication_id: str
    state: CommState = CommState.QUEUED
    state_timestamps: dict[CommState, datetime] = field(default_factory=dict)
    failed: bool = False
    failure_reason: str | None = None
    last_event_at: datetime | None = None
    event_count: int = 0

    def apply(self, event: CommEvent) -> "CommProjection":
        """Fold a single event into the projection. Pure and order-independent:
        applying the same set of events in any order yields the same `state`."""
        self.event_count += 1

        # Record the timestamp for this state the first time we see it. Earlier
        # event-time wins if duplicates disagree (clock skew / replays).
        prev = self.state_timestamps.get(event.event_type)
        if prev is None or event.occurred_at < prev:
            self.state_timestamps[event.event_type] = event.occurred_at

        if self.last_event_at is None or event.received_at > self.last_event_at:
            self.last_event_at = event.received_at

        if can_advance(self.state, event.event_type):
            self.state = event.event_type
            if event.event_type is CommState.FAILED:
                self.failed = True
                self.failure_reason = event.meta.get("reason")
        return self

    @classmethod
    def from_events(cls, communication_id: str, events: list[CommEvent]) -> "CommProjection":
        """Rebuild a projection from scratch. Used for replay/audit and to prove
        order-independence in tests: shuffle the list, get the same state."""
        proj = cls(communication_id=communication_id)
        # Sort by rank then event-time so the fold is deterministic regardless of
        # arrival order; can_advance still guards every step.
        for ev in sorted(events, key=lambda e: (rank(e.event_type), e.occurred_at)):
            proj.apply(ev)
        return proj


def fold(communication_id: str, events: list[CommEvent]) -> CommProjection:
    """Convenience wrapper mirroring `CommProjection.from_events`."""
    return CommProjection.from_events(communication_id, events)
