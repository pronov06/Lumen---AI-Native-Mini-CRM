"""The live delivery feed WebSocket — the showpiece.

A client connects to /ws/feed and receives every projection update in real time:
each delivered/opened/read/clicked/failed as it folds in. The CRM publishes these
to the bus on ingest; this endpoint subscribes and forwards.

Best-effort by design: the database is the source of truth, the feed is a live
view of it. A dropped frame is recoverable by refetching stats; we never block
ingest on a slow socket.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/feed")
async def feed(ws: WebSocket) -> None:
    await ws.accept()
    bus = ws.app.state.bus
    await ws.send_json({"type": "feed.connected"})

    async def pump() -> None:
        async for update in bus.subscribe_updates():
            await ws.send_json(update)

    pump_task = asyncio.create_task(pump())
    try:
        # Keep the socket alive; surface client disconnects promptly.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
