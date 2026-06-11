"""Campaign / audience statistics, derived from communication projections.

Every number here traces to ingested events — there is no free-floating
"open rate". A communication contributes to a funnel stage if it ever *reached*
that stage (recorded in `state_timestamps`), which is what makes the counts
correct even when callbacks arrive out of order. Failures are counted from the
terminal `failed` flag, not inferred.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .lifecycle import CommState
from .projection import CommProjection


@dataclass(slots=True)
class FunnelStats:
    queued: int = 0
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    read: int = 0
    clicked: int = 0
    failed: int = 0
    total: int = 0

    # Rates are computed against the meaningful denominator, not the total, so
    # they read the way a marketer expects (open rate = opened / delivered).
    @property
    def delivery_rate(self) -> float:
        return _safe(self.delivered, self.sent)

    @property
    def open_rate(self) -> float:
        return _safe(self.opened, self.delivered)

    @property
    def click_rate(self) -> float:
        return _safe(self.clicked, self.delivered)

    @property
    def failure_rate(self) -> float:
        return _safe(self.failed, self.total)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(
            delivery_rate=round(self.delivery_rate, 4),
            open_rate=round(self.open_rate, 4),
            click_rate=round(self.click_rate, 4),
            failure_rate=round(self.failure_rate, 4),
        )
        return d


def _safe(num: int, den: int) -> float:
    return (num / den) if den else 0.0


# A comm that reached READ also counts as delivered and opened — the funnel is
# cumulative. We read that from state_timestamps, which records every stage the
# comm passed through even if the headline state jumped ahead out of order.
_CUMULATIVE = [
    CommState.SENT,
    CommState.DELIVERED,
    CommState.OPENED,
    CommState.READ,
    CommState.CLICKED,
]


def aggregate(projections: list[CommProjection]) -> FunnelStats:
    s = FunnelStats(total=len(projections))
    for p in projections:
        if p.failed:
            s.failed += 1
            # A failed comm may still have been queued/sent before failing.
            if CommState.SENT in p.state_timestamps:
                s.sent += 1
            else:
                s.queued += 1
            continue
        if p.state is CommState.QUEUED:
            s.queued += 1
        seen = p.state_timestamps
        if CommState.SENT in seen:
            s.sent += 1
        if CommState.DELIVERED in seen:
            s.delivered += 1
        if CommState.OPENED in seen:
            s.opened += 1
        if CommState.READ in seen:
            s.read += 1
        if CommState.CLICKED in seen:
            s.clicked += 1
    return s
