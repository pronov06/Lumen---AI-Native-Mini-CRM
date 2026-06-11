"""The simulator — the channel service's brain.

Given a send, it produces a *plan*: a list of (delay_ms, event) the recipient
would generate. It then deliberately roughens that plan — shuffling some comms'
events so callbacks arrive out of order, and duplicating some — before handing
each event to a `poster` that ships it to the CRM's /receipts.

This separation (plan vs. post) is what makes the channel testable and lets the
same simulator run behind the HTTP service and inside the integration test.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# The lifecycle vocabulary, duplicated by design — the channel does not import
# the CRM's code. The two services agree on these strings by contract only.
DELIVERED = "delivered"
FAILED = "failed"
OPENED = "opened"
READ = "read"
CLICKED = "clicked"


@dataclass(slots=True)
class PlannedEvent:
    event_type: str
    provider_event_id: str
    delay_ms: int


@dataclass(slots=True)
class SimConfig:
    failure_rate: float
    open_rate: float
    read_rate: float
    click_rate: float
    out_of_order_rate: float
    duplicate_rate: float
    min_latency_ms: int
    max_latency_ms: int


# A poster ships one callback dict to the CRM. Injected so transport is swappable.
Poster = Callable[[dict], Awaitable[None]]


class Simulator:
    def __init__(self, config: SimConfig, rng: random.Random | None = None):
        self.cfg = config
        self.rng = rng or random.Random()

    def plan(self, communication_id: str) -> list[PlannedEvent]:
        """Decide what this recipient does. Each stage is conditional on the
        previous, so the funnel narrows the way a real one does."""
        cfg, rng = self.cfg, self.rng
        n = 0

        def pid() -> str:
            nonlocal n
            n += 1
            return f"{communication_id}-evt-{n}"

        def latency() -> int:
            return rng.randint(cfg.min_latency_ms, cfg.max_latency_ms)

        events: list[PlannedEvent] = []
        if rng.random() < cfg.failure_rate:
            events.append(PlannedEvent(FAILED, pid(), latency()))
            return events

        events.append(PlannedEvent(DELIVERED, pid(), latency()))
        if rng.random() < cfg.open_rate:
            events.append(PlannedEvent(OPENED, pid(), latency()))
            if rng.random() < cfg.read_rate:
                events.append(PlannedEvent(READ, pid(), latency()))
                if rng.random() < cfg.click_rate:
                    events.append(PlannedEvent(CLICKED, pid(), latency()))
        return events

    def _roughen(self, events: list[PlannedEvent]) -> list[PlannedEvent]:
        """Inject the two real-world hazards the CRM must survive."""
        out = list(events)
        if self.rng.random() < self.cfg.out_of_order_rate:
            self.rng.shuffle(out)  # callbacks arrive scrambled
        roughened: list[PlannedEvent] = []
        for ev in out:
            roughened.append(ev)
            if self.rng.random() < self.cfg.duplicate_rate:
                roughened.append(ev)  # at-least-once: same event twice
        return roughened

    async def run(self, *, communication_id: str, recipient: str, channel: str,
                  poster: Poster) -> None:
        """Execute the (roughened) plan, posting each callback after its delay."""
        plan = self._roughen(self.plan(communication_id))
        for ev in plan:
            await asyncio.sleep(ev.delay_ms / 1000.0)
            payload = {
                "communication_id": communication_id,
                "event_type": ev.event_type,
                "provider_event_id": ev.provider_event_id,
                "channel": channel,
                "recipient": recipient,
                "meta": {"reason": "hard_bounce"} if ev.event_type == FAILED else {},
            }
            await poster(payload)
