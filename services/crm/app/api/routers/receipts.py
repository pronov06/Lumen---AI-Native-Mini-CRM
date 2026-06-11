"""Receipts route — the inbound half of the callback loop.

Every delivery signal (delivered/opened/read/clicked/failed) the channel service
observes is POSTed here. This endpoint is internet-reachable, so it is the one
place an attacker could try to forge stats. Two defenses, in order:

  1. HMAC-SHA256 over the *raw* request body with the shared secret. No valid
     signature -> 401 and the event never touches the log.
  2. Idempotent ingest. The same callback delivered twice (at-least-once) folds
     to the same projection; duplicates are no-ops.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.deps import bus_dep, settings_dep
from app.core.bus import Bus
from app.core.config import Settings
from app.core.ingest import Ingestor
from app.core.signing import verify
from app.infra.repo import Repo

router = APIRouter(tags=["receipts"])


@router.post("/receipts")
async def receipts(
    request: Request,
    x_signature: str | None = Header(default=None),
    settings: Settings = Depends(settings_dep),
    bus: Bus = Depends(bus_dep),
) -> dict:
    raw = await request.body()
    if not verify(raw, x_signature or "", settings.callback_secret):
        raise HTTPException(401, "invalid signature")

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "malformed JSON")

    comm_id = body.get("communication_id")
    event_type = body.get("event_type")
    provider_event_id = body.get("provider_event_id")
    if not (comm_id and event_type and provider_event_id):
        raise HTTPException(422, "missing required callback fields")

    factory = request.app.state.session_factory
    locks = request.app.state.locks
    async with factory() as session:
        ingestor = Ingestor(Repo(session), bus, locks)
        try:
            result = await ingestor.ingest(
                communication_id=comm_id,
                event_type=event_type,
                provider_event_id=provider_event_id,
                meta=body.get("meta") or {},
            )
        except ValueError:
            await session.rollback()
            raise HTTPException(422, f"unknown event_type {event_type!r}")
    # 200 even for duplicate/unknown so the channel doesn't retry benign cases.
    return result
