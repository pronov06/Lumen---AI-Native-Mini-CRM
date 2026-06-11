"""Unit tests for the pure domain core.

These prove the four properties the whole loop depends on, with zero infra:
  - monotonic state (out-of-order callbacks never regress)
  - idempotency (duplicate events are no-ops for state)
  - order-independence (any permutation folds to the same state)
  - stat correctness + DSL injection safety
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.lifecycle import CommState, can_advance, is_terminal
from app.domain.projection import CommEvent, CommProjection
from app.domain.segment import SegmentError, compile_segment, parse_segment
from app.domain.stats import aggregate

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def ev(cid: str, state: CommState, n: int = 0, secs: int = 0) -> CommEvent:
    t = NOW + timedelta(seconds=secs)
    return CommEvent(
        communication_id=cid,
        event_type=state,
        provider_event_id=f"prov-{state.value}-{n}",
        occurred_at=t,
        received_at=t,
        meta={"reason": "hard_bounce"} if state is CommState.FAILED else {},
    )


# --- lifecycle ---------------------------------------------------------------

def test_state_advances_forward():
    assert can_advance(CommState.SENT, CommState.DELIVERED)
    assert can_advance(CommState.DELIVERED, CommState.CLICKED)


def test_state_never_regresses():
    assert not can_advance(CommState.DELIVERED, CommState.SENT)
    assert not can_advance(CommState.READ, CommState.DELIVERED)


def test_failed_is_terminal():
    assert is_terminal(CommState.FAILED)
    assert not can_advance(CommState.FAILED, CommState.DELIVERED)
    assert not can_advance(CommState.FAILED, CommState.CLICKED)


def test_clicked_is_absorbing():
    assert is_terminal(CommState.CLICKED)
    assert not can_advance(CommState.CLICKED, CommState.OPENED)


def test_failure_supersedes_in_progress():
    # A send that's only 'sent' can still fail.
    assert can_advance(CommState.SENT, CommState.FAILED)


# --- projection: out-of-order + idempotency ----------------------------------

def test_read_before_delivered_jumps_forward_records_both():
    p = CommProjection(communication_id="c1")
    p.apply(ev("c1", CommState.SENT, secs=0))
    p.apply(ev("c1", CommState.READ, secs=1))      # arrives early
    p.apply(ev("c1", CommState.DELIVERED, secs=2))  # the straggler
    assert p.state is CommState.READ                # state did not regress
    # but we still recorded *when* delivery happened, for the funnel
    assert CommState.DELIVERED in p.state_timestamps
    assert CommState.READ in p.state_timestamps


def test_duplicate_event_is_state_noop():
    p = CommProjection(communication_id="c1")
    p.apply(ev("c1", CommState.DELIVERED))
    p.apply(ev("c1", CommState.DELIVERED))  # exact duplicate
    p.apply(ev("c1", CommState.DELIVERED))
    assert p.state is CommState.DELIVERED
    # event_count rises (we log every arrival) but state is stable
    assert p.event_count == 3


def test_order_independence_under_shuffle():
    events = [
        ev("c1", CommState.SENT, secs=0),
        ev("c1", CommState.DELIVERED, secs=1),
        ev("c1", CommState.OPENED, secs=2),
        ev("c1", CommState.READ, secs=3),
        ev("c1", CommState.CLICKED, secs=4),
    ]
    states = set()
    for _ in range(50):
        random.shuffle(events)
        states.add(CommProjection.from_events("c1", list(events)).state)
    assert states == {CommState.CLICKED}  # always lands on the same state


def test_failure_then_late_positive_stays_failed():
    p = CommProjection(communication_id="c1")
    p.apply(ev("c1", CommState.SENT, secs=0))
    p.apply(ev("c1", CommState.FAILED, secs=1))
    p.apply(ev("c1", CommState.DELIVERED, secs=2))  # straggler after failure
    assert p.state is CommState.FAILED
    assert p.failed and p.failure_reason == "hard_bounce"


# --- stats -------------------------------------------------------------------

def test_funnel_is_cumulative_and_traceable():
    # 3 comms: one clicked, one delivered-only, one failed-after-send
    c1 = CommProjection.from_events("c1", [
        ev("c1", CommState.SENT), ev("c1", CommState.DELIVERED),
        ev("c1", CommState.OPENED), ev("c1", CommState.CLICKED),
    ])
    c2 = CommProjection.from_events("c2", [
        ev("c2", CommState.SENT), ev("c2", CommState.DELIVERED),
    ])
    c3 = CommProjection.from_events("c3", [
        ev("c3", CommState.SENT), ev("c3", CommState.FAILED),
    ])
    s = aggregate([c1, c2, c3])
    assert s.total == 3
    assert s.sent == 3
    assert s.delivered == 2     # c1, c2 (c3 failed)
    assert s.opened == 1        # c1 only
    assert s.clicked == 1       # c1 only
    assert s.failed == 1        # c3
    assert s.open_rate == pytest.approx(0.5)   # 1 opened / 2 delivered
    assert s.click_rate == pytest.approx(0.5)  # 1 clicked / 2 delivered


# --- segment DSL safety ------------------------------------------------------

def test_valid_segment_compiles_to_parameterized_sql():
    seg = parse_segment({
        "match": "all",
        "rules": [
            {"field": "total_orders", "op": "gte", "value": 1},
            {"field": "days_since_last_order", "op": "gt", "value": 60},
        ],
    })
    where, params = compile_segment(seg, now=NOW)
    assert ":p0" in where and ":p1" in where  # values are bound, not inlined
    assert params["p0"] == 1 and params["p1"] == 60


def test_unknown_field_is_rejected():
    with pytest.raises(SegmentError):
        parse_segment({"rules": [{"field": "password", "op": "eq", "value": "x"}]})


def test_sql_injection_value_is_neutralized_as_a_bound_param():
    # Even a malicious value can't break out — it becomes a bound parameter.
    seg = parse_segment({"rules": [{"field": "city", "op": "eq",
                                    "value": "'; DROP TABLE customers;--"}]})
    where, params = compile_segment(seg, now=NOW)
    assert "DROP TABLE" not in where               # never in the SQL text
    assert params["p0"] == "'; DROP TABLE customers;--"  # safely a value


def test_bad_op_for_field_rejected():
    with pytest.raises(SegmentError):
        parse_segment({"rules": [{"field": "total_orders", "op": "in", "value": 5}]})
