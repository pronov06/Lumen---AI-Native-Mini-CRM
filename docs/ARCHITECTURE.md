# Architecture

## Two services, one HTTP boundary

The brief asks for a system that decides who to message and measures the result. The interesting engineering is in *measuring the result*, because real delivery is asynchronous and unreliable. So the design splits along the same seam a production CRM does:

- **CRM service** owns the truth — customers, orders, campaigns, and the communication event log — plus segmentation, the AI co-pilot, the projection, stats, and the WebSocket fan-out.
- **Channel service** is a stand-in for a messaging provider (WhatsApp / SMS / Email / RCS). It accepts a send, then asynchronously posts back signed callbacks with realistic imperfection: latency, reordering, duplicates, and failures.

They share no code and no database. The only contract between them is HTTP: the CRM `POST`s to `/v1/send`; the channel `POST`s signed receipts back to `/receipts`. This is what makes the system a genuine distributed-systems exercise rather than a single process pretending to be two.

## Event sourcing on the communication

A communication moves through a lifecycle:

```
queued → sent → delivered → opened → read → clicked
                    │
                    └────────────► failed   (terminal)
```

`/receipts` never updates a status column. It **appends an immutable event** to `communication_events`, then re-derives the communication's state by folding the whole event log:

```
events ─(sort by lifecycle rank, then time)─► fold ─► projection ─► cache row
```

Each lifecycle state has a monotonic **rank**. The fold takes the highest-rank state reached and records a timestamp for *every* stage seen, even when an event arrives that "skips" or "rewinds." Three properties fall out of this for free:

| Property | How the design gives it |
| --- | --- |
| **Out-of-order safety** | The fold sorts by rank, so a late `delivered` after a `read` can't move state backward — and the `delivered` timestamp is still captured. |
| **Idempotency** | A unique key `(communication_id, event_type, provider_event_id)` rejects duplicate callbacks at the database. Replays are no-ops. |
| **Auditability / replay** | The log is authoritative; the cached projection row is a derived read-model that can be rebuilt by re-folding. |

At-least-once delivery (the channel retries) plus idempotent ingest gives **effectively-once** processing.

## The concurrency model

Two writers touch a single communication concurrently: the **send worker** (recording `sent` after the channel acks) and the **receipts endpoint** (recording inbound callbacks). Both do a read-modify-write on the cached projection row — append an event, re-fold, write the row. Done naively, the later commit clobbers the earlier with a stale fold. The fix has three layers, each correct for a different deployment:

1. **Idempotent insert via `SAVEPOINT`.** The event insert runs inside a nested transaction so a duplicate rolls back only the savepoint, never the outer transaction, and never expires the loaded row.
2. **Per-communication keyed async lock.** Within a process, the read-modify-write-commit for a given `communication_id` is serialized. Different communications still run concurrently.
3. **`SELECT … FOR UPDATE` row lock.** For a multi-instance deployment (several CRM replicas behind Postgres + Redis), the row lock serializes writers across processes, where the in-process lock can't reach. It's a no-op on SQLite, which the keyed lock covers.

The append-only log means even if a projection row ever did go stale, the data isn't lost — re-folding the events reconstructs the correct state. The cache is an optimization, not the source of truth.

## Ports and adapters

The domain layer — lifecycle ranks, the projection fold, the segment DSL, funnel math — is pure Python with no I/O. Everything stateful sits behind a port:

- **Repository** — persistence. Postgres (`asyncpg`) in prod, SQLite (`aiosqlite`) in dev/test, same interface.
- **Bus** — the send queue and the pub/sub fan-out to WebSocket clients. Redis in prod, an in-process `asyncio` implementation in dev/test.
- **Channel client** — the outbound HTTP call to the channel. A fake is injected in the integration test to force the retry/dead-letter path.

Because the ports are swappable, the test suite exercises the *real* domain and application logic against in-memory adapters, and the e2e test exercises the real adapters against real HTTP.

## Segmentation as a trust boundary

The co-pilot turns a natural-language goal into a small **typed segment DSL**: a closed set of fields (`total_orders`, `total_spend`, `days_since_last_order`, `lifecycle_stage`, `channel_optin`, `city`, …) and a validated set of operators. The DSL is parsed at a single trust boundary and compiled to **parameterized** SQL.

The model never emits SQL — it emits DSL — so prompt-injection in a goal string has no SQL surface to reach. A goal like *"lapsed customers'); DROP TABLE …"* simply fails DSL validation. This is covered by unit tests that feed hostile input through the parser.

## Safety on the callback path

`/receipts` verifies an HMAC-SHA256 signature over the raw request body against a shared secret before doing anything. A forged or tampered callback is rejected with `401` (verified in the e2e test). Outbound calls (sends and callbacks) share a retry policy with backoff and jitter; exhausted retries are written to a dead-letter table rather than silently dropped, and the affected communication is marked failed.

## Why SQLite *and* Postgres

SQLite is the zero-infrastructure path: the CRM boots against a local file with an in-process bus, so the whole app — and the entire test suite, including the two-service e2e — runs with nothing else installed. Postgres is the production path for real concurrency and durability. The repository port keeps both honest by forcing the same code down both.
