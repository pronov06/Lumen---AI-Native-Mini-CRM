"""Campaign routes — the spine of the product.

Lifecycle, with the human gate in the middle:

    create  -> status=draft     (segment validated, audience sized, nothing sent)
    approve -> status=sending    (fan out one communication per recipient,
               -> status=sent     enqueue each send; the worker takes it from here)

`approve` is the only thing that ever puts messages in flight, and it can only
act on a draft — so a campaign cannot be sent twice, and nothing is sent without
an explicit human action. Everything after dispatch (delivered/opened/…) arrives
asynchronously through /receipts and is read back via /stats.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api._helpers import customer_eval_dict, recipient_for
from app.api.deps import bus_dep, repo_dep
from app.api.schemas import CampaignCreate
from app.core.bus import Bus
from app.domain.segment import SegmentError, evaluate_segment, parse_segment
from app.domain.stats import aggregate
from app.infra import models
from app.infra.repo import Repo

router = APIRouter(tags=["campaigns"])

CHANNELS = {"whatsapp", "sms", "email", "rcs"}


def _campaign_out(c: models.Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "channel": c.channel,
        "message": c.message,
        "status": c.status,
        "recipient_count": c.recipient_count,
        "segment": c.segment_json,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
    }


@router.post("/campaigns", status_code=201)
async def create_campaign(
    body: CampaignCreate,
    repo: Repo = Depends(repo_dep),
) -> dict:
    if body.channel not in CHANNELS:
        raise HTTPException(422, f"unknown channel {body.channel!r}")
    try:
        seg = parse_segment(body.segment)
    except SegmentError as exc:
        raise HTTPException(422, f"invalid segment: {exc}")

    customers = [customer_eval_dict(c) for c in await repo.list_customers()]
    matched = evaluate_segment(seg, customers, now=datetime.now(timezone.utc))

    campaign = models.Campaign(
        id=f"cmp_{uuid.uuid4().hex[:12]}",
        name=body.name,
        channel=body.channel,
        message=body.message,
        segment_json=body.segment,
        status="draft",
        recipient_count=len(matched),
    )
    await repo.create_campaign(campaign)
    return _campaign_out(campaign)


@router.get("/campaigns")
async def list_campaigns(repo: Repo = Depends(repo_dep)) -> dict:
    rows = await repo.list_campaigns()
    return {"campaigns": [_campaign_out(c) for c in rows]}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, repo: Repo = Depends(repo_dep)) -> dict:
    c = await repo.get_campaign(campaign_id)
    if c is None:
        raise HTTPException(404, "campaign not found")
    return _campaign_out(c)


@router.post("/campaigns/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: str,
    repo: Repo = Depends(repo_dep),
    bus: Bus = Depends(bus_dep),
) -> dict:
    campaign = await repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(404, "campaign not found")
    if campaign.status != "draft":
        # The gate: only a draft can be approved. Idempotent against double-clicks.
        raise HTTPException(409, f"campaign is '{campaign.status}', not 'draft'")

    seg = parse_segment(campaign.segment_json)
    customers = await repo.list_customers()
    by_id = {c.id: c for c in customers}
    eval_dicts = [customer_eval_dict(c) for c in customers]
    matched = evaluate_segment(seg, eval_dicts, now=datetime.now(timezone.utc))

    # Fan out: one communication per recipient, all starting QUEUED.
    comms: list[models.Communication] = []
    payloads: list[dict] = []
    for m in matched:
        cust = by_id[m["id"]]
        comm_id = f"com_{uuid.uuid4().hex[:14]}"
        recipient = recipient_for(campaign.channel, cust)
        comms.append(models.Communication(
            id=comm_id,
            campaign_id=campaign.id,
            customer_id=cust.id,
            channel=campaign.channel,
            recipient=recipient,
            state="queued",
        ))
        payloads.append({
            "communication_id": comm_id,
            "recipient": recipient,
            "message": campaign.message,
            "channel": campaign.channel,
        })

    await repo.create_communications(comms)
    await repo.set_campaign_status(campaign.id, "sending")
    # Commit comms + status BEFORE enqueueing, so the worker (and any callback
    # that races back) always finds the communication row already persisted.
    await repo.s.commit()

    for p in payloads:
        await bus.enqueue_send(p)

    await repo.set_campaign_status(
        campaign.id, "sent", sent_at=datetime.now(timezone.utc)
    )
    return {
        "campaign_id": campaign.id,
        "status": "sent",
        "dispatched": len(payloads),
    }


@router.get("/campaigns/{campaign_id}/stats")
async def campaign_stats(campaign_id: str, repo: Repo = Depends(repo_dep)) -> dict:
    campaign = await repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(404, "campaign not found")
    projections = await repo.campaign_projections(campaign_id)
    funnel = aggregate(projections)
    attributed = await repo.attributed_order_count(campaign_id)
    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "recipient_count": campaign.recipient_count,
        "funnel": funnel.to_dict(),
        "attributed_orders": attributed,
    }


@router.get("/campaigns/{campaign_id}/communications")
async def campaign_communications(
    campaign_id: str, repo: Repo = Depends(repo_dep)
) -> dict:
    comms = await repo.list_communications(campaign_id)
    return {
        "communications": [
            {
                "id": c.id,
                "recipient": c.recipient,
                "channel": c.channel,
                "state": c.state,
                "failed": c.failed,
                "failure_reason": c.failure_reason,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in comms
        ]
    }
