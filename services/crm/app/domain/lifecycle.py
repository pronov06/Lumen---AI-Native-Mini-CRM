"""The communication lifecycle — the single source of truth for what a message
*can* do as it moves through the channel.

This module is deliberately free of FastAPI, SQLAlchemy, Redis and any I/O. It is
pure data + functions so the loop's hardest behaviours (out-of-order callbacks,
idempotency, monotonic state) can be unit-tested in microseconds with no infra.

The two rules the whole callback loop rests on:

  1. State only ever *advances*. A communication's state is a projection over an
     append-only event log, and a late lower-rank event (a `read` that lands
     before its `delivered`) updates timestamps but never rolls the state back.
  2. `failed` is terminal. Once a send hard-fails it cannot later be reported
     delivered/opened by a straggling callback.
"""

from __future__ import annotations

from enum import Enum


class CommState(str, Enum):
    """States a single per-recipient communication can occupy.

    The string values are the wire/DB representation; the *rank* (below) is what
    enforces monotonic progression, never this declaration order.
    """

    QUEUED = "queued"        # accepted by CRM, not yet handed to the channel
    SENT = "sent"            # channel acknowledged the send request
    DELIVERED = "delivered"  # reached the recipient's device
    OPENED = "opened"        # recipient opened it
    READ = "read"            # recipient read it (stronger than opened)
    CLICKED = "clicked"      # recipient clicked a link — the conversion signal
    FAILED = "failed"        # terminal failure (bounce, invalid recipient, ...)


# Rank defines the *happy-path* ordering. A higher rank may only be reached from
# a lower one. FAILED sits outside this ladder: it is terminal and reachable from
# any non-clicked state, but nothing escapes it.
_RANK: dict[CommState, int] = {
    CommState.QUEUED: 0,
    CommState.SENT: 1,
    CommState.DELIVERED: 2,
    CommState.OPENED: 3,
    CommState.READ: 4,
    CommState.CLICKED: 5,
}

#: States from which a comm may still transition. CLICKED/FAILED are absorbing.
TERMINAL_STATES: frozenset[CommState] = frozenset({CommState.FAILED})

#: The set of event types the channel service is allowed to report back.
#: (QUEUED is internal — the CRM sets it on enqueue, the channel never reports it.)
REPORTABLE_STATES: frozenset[CommState] = frozenset(
    s for s in CommState if s is not CommState.QUEUED
)


def rank(state: CommState) -> int:
    """Lifecycle rank used for monotonic comparison. FAILED is ranked above the
    ladder so that once failed, no positive event can supersede it."""
    if state is CommState.FAILED:
        return 99
    return _RANK[state]


def is_terminal(state: CommState) -> bool:
    return state in TERMINAL_STATES or state is CommState.CLICKED


def can_advance(current: CommState, incoming: CommState) -> bool:
    """Decide whether an incoming reported state should become the new current
    state. This is the *entire* out-of-order policy in one function.

    Examples it must get right:
      can_advance(SENT, DELIVERED)  -> True   (normal progression)
      can_advance(DELIVERED, SENT)  -> False  (stale/replayed lower-rank event)
      can_advance(SENT, READ)       -> True   (read arrived before delivered; we
                                               jump forward, delivered fills in
                                               later via timestamps, not state)
      can_advance(FAILED, DELIVERED)-> False  (failed is terminal)
      can_advance(CLICKED, OPENED)  -> False  (clicked is the top, absorbing)
    """
    # Nothing escapes a terminal state.
    if is_terminal(current):
        return False
    # A failure always wins over any in-progress positive state.
    if incoming is CommState.FAILED:
        return True
    # Otherwise advance only strictly forward along the ladder.
    return rank(incoming) > rank(current)
