# Lumen — AI-native engagement console

A mini CRM for a D2C coffee brand to decide **who to message, what to say, and on which channel** — then watch delivery happen live and measure what it drove. Built as an engineering take-home.

This is an **engagement tool, not a sales CRM.** There are no deals, pipelines, leads, or tickets. The job is one loop: pick an audience, send a campaign, and learn from how people respond.

---

## The product bet

Two decisions shape everything here.

**1. The co-pilot proposes; the operator approves.** You describe a goal in plain language — *"win back lapsed customers with a 20% offer"* — and the co-pilot returns a concrete plan: a segment (with a live audience count), a channel, and a drafted message. You edit it, then **you** are the one who launches it. The AI never sends on its own. The human-in-the-loop gate is real: campaigns are created as `draft` and only a separate, explicit approval turns them into sends.

**2. Delivery is a live, honest, first-class surface.** Real messaging is asynchronous and messy — receipts arrive late, out of order, duplicated, and sometimes not at all. Most demos hide that behind a success toast. Here the **live delivery feed** is a permanent panel: every state change (sent → delivered → opened → read → clicked, or failed) streams in over a WebSocket as it happens. The funnel animates toward its settled state in front of you.

### Consciously *not* building

Scope discipline is part of the design. This deliberately leaves out: a generic CRM object model (accounts/contacts/deals), a visual segment query-builder (the co-pilot writes segments instead), multi-step journey automation, template management, user auth/RBAC, and real channel integrations. Each was cut so the two committed bets above could be built properly rather than ten things gestured at.

---

## Architecture: a two-service callback loop

The system-design centerpiece is that the two services talk **only over HTTP**, the way a real CRM talks to a real ESP/messaging provider.

```
                        approve campaign
                              │
                              ▼
   ┌─────────────────────────────────────────┐         POST /v1/send
   │              CRM service                 │ ──────────────────────────►  ┌───────────────────┐
   │  • owns the truth (customers, orders,    │                              │  Channel service  │
   │    campaigns, the event log)             │                              │  (provider sim)   │
   │  • segments + AI co-pilot                │   signed callbacks           │  • probabilistic  │
   │  • folds events into a projection        │ ◄──────────────────────────  │    outcomes       │
   │  • /ws/feed fan-out to the browser       │   POST /receipts (HMAC)      │  • latency,       │
   └─────────────────────────────────────────┘                              │    reorder, dupes │
                              │                                              └───────────────────┘
                              ▼
                     browser live feed (WebSocket)
```

**Every callback is an immutable event.** `/receipts` does not mutate a status column — it appends a `communication_event` to an append-only log. The current state of a communication is a **projection** folded over its events, ordered by a monotonic lifecycle rank. That single decision buys a lot:

- **Out-of-order safety.** A `read` that lands before its `delivered` can't move state backwards; the fold respects rank, and every stage the message passed through is still recorded.
- **Idempotency.** Each event has a unique key (`communication_id` + `event_type` + `provider_event_id`). A duplicate callback is a no-op. Combined with at-least-once delivery, ingest is effectively-once.
- **Auditability & replay.** The log is the source of truth; the fast-read projection row is a cache that can always be rebuilt.

**The domain is storage-agnostic.** Lifecycle rules, the projection fold, the segment DSL, and funnel math are pure Python behind repository / bus / channel-client ports. Production wires Postgres + Redis + HTTP; the tests wire SQLite + an in-process bus against the *same* logic.

**Segments are a trust boundary.** The co-pilot emits a small typed segment DSL (closed field set, validated operators) — never SQL. The DSL compiles to parameterized queries. An injection attempt in a goal string can't reach the database because the model never produces SQL in the first place. This is covered by tests.

There's a deeper walkthrough — including the concurrency model — in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Running it

### Full stack (Docker)

```bash
cp .env.example .env        # optional: add an OpenRouter key for the live planner
make up                     # or: docker compose up --build
```

Then open **http://localhost:8080**, click **Seed data**, and compose a campaign. Postgres, Redis, the channel simulator, and the CRM all come up together; the web app is served as a static bundle by nginx.

### Local, no Docker

Three terminals (the services are independent):

```bash
make dev-channel    # channel simulator on :8001
make dev-crm        # CRM on :8000 (SQLite file, in-process bus — zero infra)
make dev-web        # Vite dev server on :5173
```

The CRM boots against a local SQLite file with an in-process bus, so it runs with no external dependencies at all. Set `OPENROUTER_API_KEY` to use the real AI planner; without it, a deterministic local planner keeps the co-pilot fully functional offline.

### Tests

```bash
make test           # or: cd services/crm && pytest -q
```

---

## AI-native development

This project was built with an AI pair throughout — architecture, the domain modules, the services, and the tests. The workflow that mattered most was **proving the hard part with an adversarial test and letting it find real bugs**, rather than trusting happy-path code.

The end-to-end test spins up *both* services as real subprocesses over real HTTP, with the channel simulator turned hostile (60% reordering, 40% duplicates, 12% failure), seeds data, approves a campaign, and asserts the funnel settles correctly. Standing that test up surfaced **three genuine concurrency bugs that happy-path testing would never have caught:**

1. **Eager dispatch in the segment evaluator** — a dict-dispatch comparator evaluated every branch, so a numeric rule hit `3 in 0` and threw. Fixed with short-circuiting comparison.
2. **`MissingGreenlet` under concurrent duplicate callbacks** — a full `session.rollback()` on the idempotency conflict expired the loaded row, triggering a lazy reload outside the async greenlet. Fixed by scoping the idempotent insert to a `SAVEPOINT` so a duplicate rolls back only itself.
3. **Lost update on the projection cache** — the send worker's `sent` write and an inbound `delivered` callback for the same communication folded different snapshots of the event log; the later commit clobbered the earlier with a stale state. The event log stayed correct, but the cached row went stale. Fixed by serializing the per-communication read-modify-write with a keyed async lock, paired with a `SELECT … FOR UPDATE` row lock for the multi-instance case.

A fourth issue — a stale read snapshot from a pooled SQLite connection under WAL — was traced to the connection pool and fixed by switching the SQLite path to a fresh-connection-per-session pool. The full debugging narrative is in [`docs/AI_WORKFLOW.md`](docs/AI_WORKFLOW.md).

The point isn't that the bugs existed; it's that the development loop was built to *expose* them before they could ship.

---

## Scale assumptions & tradeoffs

The brief asks for explicit tradeoffs — *"I'd do X at scale but did Y for this scope."* Here they are, plainly:

| Concern | What I did for this scope (Y) | What I'd do at scale (X) |
| --- | --- | --- |
| **CRM instances** | Single process; per-communication serialization uses an in-process keyed lock. | Multiple replicas behind Postgres + Redis. The `SELECT … FOR UPDATE` row lock is already in the code so the per-communication guarantee holds across processes — the in-process lock just becomes redundant. |
| **Send queue** | An in-process `asyncio` queue (dev) / Redis list (prod), drained by one worker. | A real broker (Kafka / SQS) with consumer groups, partitioned by campaign so workers scale horizontally without reordering a single recipient's events. |
| **Projection** | Re-fold the full event log per communication on each event. Cheap at hundreds of events. | Incremental fold + periodic snapshots, and a separate read store, so a million-event campaign doesn't re-read history on every callback. |
| **WebSocket feed** | Every event fans out to every connected client. | Per-campaign topics, server-side aggregation, and Redis pub/sub (or a dedicated push tier) so a busy console isn't streaming everything to everyone. |
| **Datastore** | SQLite for zero-infra dev/test, Postgres for prod — same repository port. | Postgres with read replicas for the projection/read path; the write path stays on the primary. |
| **Channel** | One in-cluster stub behind a `ChannelClient` port. | Real providers (WhatsApp/SMS/Email/RCS) as adapters behind that same port — per-provider receipt formats, rate limits, and credentials, with the rest of the system unchanged. |
| **AI co-pilot** | A synchronous propose call with a deterministic local fallback. | Response caching, streaming, an eval harness on segment/message quality, and tighter guardrails on the generated DSL. |

The thing I optimized for is that **none of these require re-architecting** — each is a swap behind a port or a config change, because the boundaries (repository, bus, channel-client) were drawn for exactly this.

## Stack

- **Services:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2. CRM + a separate channel simulator.
- **State:** Postgres (prod) / SQLite (dev & test) behind the same repository port. Redis for the send queue and WebSocket fan-out in prod; an in-process bus in dev/test.
- **AI:** OpenRouter (OpenAI-compatible, strict JSON-schema) with a deterministic local planner fallback.
- **Web:** React 18 + TypeScript + Vite, token-based CSS for a controlled operator-console aesthetic, a hand-rolled live feed over native WebSockets.
- **Tests:** domain unit tests, an in-process integration test for the dead-letter path, and the full two-service callback-loop e2e test over real HTTP.

## Layout

```
services/crm/        CRM service — domain, infra, API, AI co-pilot, tests
services/channel/    channel simulator — probabilistic provider with signed callbacks
web/                 React operator console
docs/                architecture deep-dive + AI workflow log
docker-compose.yml   full stack: postgres + redis + both services + web
```
