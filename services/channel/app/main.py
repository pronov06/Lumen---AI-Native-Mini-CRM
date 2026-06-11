"""Channel service HTTP surface.

POST /v1/send accepts a send and returns 202 immediately — delivery is async.
A background task runs the simulator; each resulting callback is POSTed to the
CRM's /receipts, HMAC-signed, with exponential backoff + jitter, dead-lettered
to the log after exhausting retries (never silently dropped).

This service imports nothing from the CRM. The two agree by HTTP contract only.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import random
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from app.config import get_channel_settings
from app.simulator import SimConfig, Simulator

log = logging.getLogger("channel")
logging.basicConfig(level=logging.INFO)


class SendRequest(BaseModel):
    communication_id: str
    recipient: str
    message: str
    channel: str
    callback_url: str


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: dict,
                           secret: str, *, max_attempts: int, base_ms: int,
                           cap_ms: int) -> None:
    body = json.dumps(payload).encode()
    headers = {"content-type": "application/json",
               "x-signature": _sign(body, secret)}
    last: Exception | None = None
    for attempt in range(max_attempts):
        try:
            resp = await client.post(url, content=body, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt + 1 >= max_attempts:
                break
            delay = min(cap_ms, base_ms * (2 ** attempt))
            await asyncio.sleep(random.uniform(0, delay) / 1000.0)
    # Dead-letter: out of attempts. In a real system this lands in a durable DLQ;
    # here we log it loudly so it's visible and never lost in silence.
    log.error("callback dead-lettered after %d attempts: %s | payload=%s",
              max_attempts, last, payload)


def build_app() -> FastAPI:
    cfg = get_channel_settings()
    rng = random.Random(cfg.seed) if cfg.seed is not None else random.Random()
    sim = Simulator(
        SimConfig(
            failure_rate=cfg.failure_rate, open_rate=cfg.open_rate,
            read_rate=cfg.read_rate, click_rate=cfg.click_rate,
            out_of_order_rate=cfg.out_of_order_rate, duplicate_rate=cfg.duplicate_rate,
            min_latency_ms=cfg.min_latency_ms, max_latency_ms=cfg.max_latency_ms,
        ),
        rng=rng,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = httpx.AsyncClient()
        yield
        await app.state.client.aclose()

    app = FastAPI(title="Xeno Channel Service", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "channel"}

    @app.post("/v1/send", status_code=202)
    async def send(req: SendRequest, background: BackgroundTasks) -> dict:
        async def poster(payload: dict) -> None:
            await _post_with_retry(
                app.state.client, req.callback_url, payload, cfg.callback_secret,
                max_attempts=cfg.retry_max_attempts,
                base_ms=cfg.retry_base_delay_ms, cap_ms=cfg.retry_max_delay_ms,
            )

        background.add_task(
            sim.run, communication_id=req.communication_id,
            recipient=req.recipient, channel=req.channel, poster=poster,
        )
        return {"accepted": True, "communication_id": req.communication_id}

    return app


app = build_app()
