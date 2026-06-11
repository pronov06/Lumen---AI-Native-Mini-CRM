"""Data routes: seed the demo dataset and read customers.

Seeding is idempotent — it wipes prior demo data first so a reviewer can hit the
button repeatedly and always land in the same known state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import repo_dep
from app.api.schemas import SeedRequest
from app.infra import models
from app.infra.repo import Repo
from app.seed.data import generate

router = APIRouter(tags=["data"])


@router.post("/seed")
async def seed(req: SeedRequest, repo: Repo = Depends(repo_dep)) -> dict:
    customers, orders = generate(n_customers=req.n_customers, seed=req.seed)
    await repo.reset_all()
    await repo.upsert_customers(customers)
    await repo.add_orders(orders)
    return {
        "status": "ok",
        "customers": len(customers),
        "orders": len(orders),
        "brand": "Lumen Coffee Co.",
    }


@router.get("/customers")
async def list_customers(
    limit: int = Query(default=50, ge=1, le=500),
    repo: Repo = Depends(repo_dep),
) -> dict:
    rows = await repo.list_customers()
    total = len(rows)
    sample = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "city": c.city,
            "lifecycle_stage": c.lifecycle_stage,
            "channel_optin": c.channel_optin,
            "total_orders": c.total_orders,
            "total_spend": c.total_spend,
            "avg_order_value": c.avg_order_value,
        }
        for c in rows[:limit]
    ]
    return {"total": total, "customers": sample}


@router.get("/customers/stats")
async def customer_stats(repo: Repo = Depends(repo_dep)) -> dict:
    rows = await repo.list_customers()
    by_stage: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for c in rows:
        by_stage[c.lifecycle_stage] = by_stage.get(c.lifecycle_stage, 0) + 1
        by_channel[c.channel_optin] = by_channel.get(c.channel_optin, 0) + 1
    return {"total": len(rows), "by_stage": by_stage, "by_channel": by_channel}
