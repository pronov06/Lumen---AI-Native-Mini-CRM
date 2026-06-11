# AI-native development workflow

This project was built with an AI pair across the whole stack. This note records how, because the method is the point - not just that AI wrote code, but that the loop was designed to catch the code being wrong.

## The method: prove the hard part adversarially

The risky part of this system is the asynchronous callback loop. Code that looks correct on the happy path routinely falls apart under reordering, duplicates, and concurrent writes. So before trusting any of it, the loop was pinned down by an end-to-end test that runs both services as real subprocesses over real HTTP, with the channel simulator configured to be hostile:

- 60% of callback sequences reordered
- 40% of callbacks duplicated
- 12% hard failures
- millisecond-scale random latency

The test seeds data, previews a segment, creates a draft, approves it (the HITL gate), then polls until the funnel settles - asserting the funnel is cumulative and monotonic, that nothing is stuck queued, that a forged callback is rejected `401`, that duplicates are idempotent, and that order attribution never exceeds clicks.

Standing that test up is what produced the value. It failed in ways that pointed at real defects, each of which was diagnosed by reproducing it against running servers and reading the logs.

## The bugs it found

### 1. Eager dispatch in the segment evaluator

The in-memory segment evaluator used a dict of comparators. Python builds every value in a dict literal eagerly, so the `in` comparator (`left in right`) was evaluated even for numeric rules - producing `3 in 0` and a `TypeError`. The fix was explicit short-circuiting branches so only the selected operator runs. Lesson: dict-dispatch over comparisons is a trap in Python.

### 2. `MissingGreenlet` under concurrent duplicate callbacks

With duplicates at 40%, `/receipts` started returning intermittent `500`s. The trace pointed at SQLAlchemy attempting I/O outside the async greenlet. Root cause: the idempotent-insert path caught the unique-constraint violation and called a full `session.rollback()`, which expired the already-loaded communication row. The next attribute access on that row triggered a lazy reload - a database round-trip - from a context that no longer had the greenlet. The dead-lettered callbacks were then lost, so communications never reached a terminal state and the settle-poll timed out.

The fix is the canonical idempotent-insert pattern: wrap the insert in a `SAVEPOINT` (`begin_nested`). A duplicate rolls back only the savepoint; the outer transaction and the loaded row are untouched.

### 3. Lost update on the projection cache

After the savepoint fix, the loop ran clean - but a handful of communications settled with a stale cached state (for example event log `[sent, delivered, read, opened, clicked]`, cached row still showing `sent`). The event log was always complete and correct; only the derived cache was wrong.

This was a classic lost update. The send worker's `sent` write and an inbound `delivered` callback for the same communication each folded a different snapshot of the event log, and whichever committed last won - sometimes with the staler fold. The fix serializes the per-communication read-modify-write with a keyed async lock, and adds a `SELECT ... FOR UPDATE` row lock so the same guarantee holds across multiple CRM instances. Crucially, because the log is authoritative, no data was ever lost - only the cache drifted, and re-folding would have corrected it anyway.

### 4. Stale read snapshot from the connection pool

A subtler one: right after seeding, one request would see 120 customers while the very next request saw zero. A pooled SQLite connection under WAL was holding a read snapshot from before the seed committed. Switching the SQLite path to a fresh-connection-per-session pool removed the stale snapshot and made cross-request reads reliably read-committed.

## A change that proved the seams

After the loop was solid, the AI co-pilot's model provider was swapped - from an OpenAI-compatible endpoint to Google Gemini 2.5 Flash - and then the whole thing was packaged into a single container for hosting. Both are the kind of change that exposes whether the boundaries were real or decorative.

The provider swap touched exactly one file: the planner adapter. The application logic, the DSL trust boundary that validates whatever the model proposes, and every test were untouched, because nothing above the planner port ever knew which model was behind it. The deployment change was similar - the two services kept their HTTP contract and simply moved to `127.0.0.1` behind a reverse proxy. Neither change required reopening the domain. That is the payoff of having drawn the ports deliberately up front: the expensive parts stayed closed when the cheap parts changed.

## What this demonstrates

Every one of these bugs is a concurrency and consistency bug - the kind that does not show up when you click through a UI, and the kind that is genuinely hard to reason about from the code alone. They were caught because the development loop was built to be adversarial first and convenient second. The final state: 29 tests green, including the full hostile two-service loop, run repeatedly to confirm stability rather than a lucky pass.
