"""CRM service entrypoint.

Builds every singleton once in the lifespan and hangs it on `app.state`, starts
the send worker as a background task, and mounts the routers. The whole object
graph is assembled here and nowhere else, so the wiring is readable in one place
and the same `build_app()` is reused verbatim by the integration test.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.copilot import Copilot
from app.api.routers import campaigns, copilot, data, ops, receipts
from app.api import ws
from app.core.bus import make_bus
from app.core.channel_client import HttpChannelClient
from app.core.config import Settings, get_settings
from app.core.locks import KeyedLocks
from app.core.sender import Sender
from app.infra.db import init_schema, make_engine, make_session_factory

log = logging.getLogger("crm")
logging.basicConfig(level=logging.INFO)


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        session_factory = make_session_factory(engine)
        await init_schema(engine)

        bus = make_bus(settings.bus, settings.redis_url)
        channel_client = HttpChannelClient(
            base_url=settings.channel_base_url,
            callback_url=f"{settings.crm_public_url}/receipts",
            secret=settings.callback_secret,
        )
        copilot_engine = Copilot(settings)
        locks = KeyedLocks()
        sender = Sender(session_factory, bus, channel_client, settings, locks)

        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.bus = bus
        app.state.channel_client = channel_client
        app.state.copilot = copilot_engine
        app.state.locks = locks
        app.state.sender = sender

        worker = asyncio.create_task(sender.run_worker())
        log.info("CRM started (bus=%s, db=%s)", settings.bus,
                 settings.database_url.split("://", 1)[0])
        try:
            yield
        finally:
            sender.stop()
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            await channel_client.aclose()
            await engine.dispose()

    app = FastAPI(title="Xeno Mini CRM", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list if settings else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(data.router)
    app.include_router(copilot.router)
    app.include_router(campaigns.router)
    app.include_router(receipts.router)
    app.include_router(ops.router)
    app.include_router(ws.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "crm"}

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": "Xeno Mini CRM",
            "product": "AI-native campaign co-pilot with a live delivery feed",
            "docs": "/docs",
        }

    return app


app = build_app()
