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
- **Planner** — the AI co-pilot's brain. A `GeminiPlanner` (Google Gemini 2.5 Flash) in prod, a deterministic `LocalPlanner` when no API key is present. The application code depends only on the planner interface, so the two are interchangeable.

Because the ports are swappable, the test suite exercises the *real* domain and application logic against in-memory adapters, and the e2e test exercises the real adapters against real HTTP.

## Segmentation as a trust boundary

The co-pilot turns a natural-language goal into a small **typed segment DSL**: a closed set of fields (`total_orders`, `total_spend`, `days_since_last_order`, `lifecycle_stage`, `channel_optin`, `city`, …) and a validated set of operators. The DSL is parsed at a single trust boundary and compiled to **parameterized** SQL.

The model never emits SQL — it emits DSL — so prompt-injection in a goal string has no SQL surface to reach. A goal like *"lapsed customers'); DROP TABLE …"* simply fails DSL validation. This is covered by unit tests that feed hostile input through the parser.

## The AI co-pilot

The co-pilot turns a plain-language goal into a structured proposal — a segment, a channel, and a drafted message. In production this is **Google Gemini 2.5 Flash**, called with a strict JSON schema so the model returns a typed object rather than free text. When no API key is configured the same interface is served by a deterministic `LocalPlanner`, so the product — and every test — works fully offline.

Two design points keep the AI from being a liability:

- **The model's output is never trusted directly.** The segment it proposes is run through the same DSL parser and validator described above. A hallucinated field or operator fails validation and is rejected; it cannot reach the database.
- **The AI proposes, it never acts.** The co-pilot only produces a `draft`. Turning a draft into real sends is a separate, explicit human approval — the model has no path to dispatch a campaign on its own.

Swapping the provider (this project moved from an OpenAI-compatible endpoint to Gemini) touched only the planner adapter; the application, the DSL trust boundary, and the tests were unchanged — which is the ports-and-adapters design paying off in a real change.

## Safety on the callback path

`/receipts` verifies an HMAC-SHA256 signature over the raw request body against a shared secret before doing anything. A forged or tampered callback is rejected with `401` (verified in the e2e test). Outbound calls (sends and callbacks) share a retry policy with backoff and jitter; exhausted retries are written to a dead-letter table rather than silently dropped, and the affected communication is marked failed.

## Why SQLite *and* Postgres

SQLite is the zero-infrastructure path: the CRM boots against a local file with an in-process bus, so the whole app — and the entire test suite, including the two-service e2e — runs with nothing else installed. Postgres is the production path for real concurrency and durability. The repository port keeps both honest by forcing the same code down both.

## Deployment topology

The system is designed to run as separate, independently-scalable services behind Postgres + Redis. It is also packaged to run as a **single container** for a free hosting tier (Hugging Face Spaces, which exposes one container on one port), and the way it collapses is itself a useful demonstration that the architecture is honest.

Inside that one container, `supervisord` runs three processes:

```
                         ┌──────────────────── container :7860 ────────────────────┐
   browser ──HTTP/WS──►  │  nginx ──/────────────────► static React bundle          │
                         │        ├─/seed /customers /campaigns /copilot ─► CRM :8000│
                         │        └─/ws/feed (Upgrade) ──────────────────► CRM :8000 │
                         │                                                            │
                         │   CRM :8000  ──POST /v1/send──►  Channel :8001             │
                         │   CRM :8000  ◄─POST /receipts──  Channel :8001 (signed)    │
                         └────────────────────────────────────────────────────────────┘
```

The key point: **the two services are not merged.** They still run as separate uvicorn processes and still talk only over HTTP — the boundary is identical to the multi-host case, the addresses are just `127.0.0.1`. nginx serves the static bundle and reverse-proxies the API routes and the WebSocket (with the `Upgrade`/`Connection` headers the live feed needs) to the CRM. The single container is a packaging constraint of the host, not an architectural compromise.

For that free tier the CRM runs the zero-infra path — SQLite plus the in-process bus — which is correct precisely because there is a single CRM process: the in-process bus and the WebSocket fan-out only need to coordinate within one process. Pointing `CRM_DATABASE_URL` at Postgres and `CRM_BUS` at Redis is the only change required to run the same image as multiple replicas, at which point the `SELECT … FOR UPDATE` row lock from the concurrency model takes over from the in-process keyed lock.
