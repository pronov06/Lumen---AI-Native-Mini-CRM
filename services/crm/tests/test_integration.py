"""In-process integration test: the send-side dead-letter guarantee.

This drives the CRM app via httpx ASGITransport (its real lifespan, real send
worker) but injects a channel client that always fails — proving that when the
channel is unreachable, every send exhausts its retries, lands in the
dead-letter queue (never silently dropped), and the communication is marked
failed rather than left stuck in QUEUED.

The *full* two-service loop (CRM <-> channel over real HTTP, with hostile
out-of-order/duplicate/failure simulation) lives in test_e2e.py, which runs both
services as real subprocesses.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import httpx
import pytest

from app.core.config import Settings
from app.main import build_app as build_crm


class FailingChannelClient:
    async def send(self, **_) -> None:
        raise httpx.ConnectError("channel down")


def _crm_settings(db_path: str) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        bus="memory",
        callback_secret="test-shared-secret",
        crm_public_url="http://crm",
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_max_delay_ms=5,
    )


@pytest.mark.asyncio
async def test_send_dead_letters_when_channel_unreachable():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    crm_app = build_crm(_crm_settings(db_path))

    async with crm_app.router.lifespan_context(crm_app):
        crm_app.state.sender.channel = FailingChannelClient()
        transport = httpx.ASGITransport(app=crm_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://crm") as api:
            await api.post("/seed", json={"n_customers": 30, "seed": 1})
            segment = {"match": "all", "rules": [
                {"field": "total_orders", "op": "gte", "value": 0}]}
            campaign = (await api.post("/campaigns", json={
                "name": "all", "segment": segment, "channel": "sms",
                "message": "hi"})).json()
            audience = campaign["recipient_count"]
            assert audience == 30
            await api.post(f"/campaigns/{campaign['id']}/approve")

            for _ in range(300):
                dl = (await api.get("/dead-letters")).json()
                if dl["count"] >= audience:
                    break
                await asyncio.sleep(0.02)
            dl = (await api.get("/dead-letters")).json()
            assert dl["count"] == audience
            assert all(d["kind"] == "send" for d in dl["dead_letters"])

            comms = (await api.get(
                f"/campaigns/{campaign['id']}/communications")).json()["communications"]
            assert all(c["state"] == "failed" for c in comms)
            funnel = (await api.get(
                f"/campaigns/{campaign['id']}/stats")).json()["funnel"]
            assert funnel["failed"] == audience

    os.unlink(db_path)
