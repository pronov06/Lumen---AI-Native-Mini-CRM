"""Operational routes: surface the dead-letter queue and a system overview.

Dead letters are deliberately first-class and visible — a send or callback that
exhausts retries lands here, never in silence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import repo_dep
from app.infra.repo import Repo

router = APIRouter(tags=["ops"])


@router.get("/dead-letters")
async def dead_letters(repo: Repo = Depends(repo_dep)) -> dict:
    rows = await repo.list_dead_letters()
    return {
        "count": len(rows),
        "dead_letters": [
            {
                "id": d.id,
                "kind": d.kind,
                "error": d.error,
                "attempts": d.attempts,
                "payload": d.payload,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ],
    }
