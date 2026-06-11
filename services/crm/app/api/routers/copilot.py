"""Co-pilot routes: turn a plain-language goal into an inspectable campaign
proposal, and preview how many real customers a segment would reach.

The preview is what makes the HITL review meaningful — the marketer sees the
audience size and a sample *before* anything is approved or sent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.ai.copilot import Copilot
from app.api._helpers import customer_eval_dict
from app.api.deps import copilot_dep, repo_dep
from app.api.schemas import CopilotRequest, SegmentPreviewRequest
from app.domain.segment import SegmentError, evaluate_segment, parse_segment
from app.infra.repo import Repo

router = APIRouter(tags=["copilot"])


def _preview(segment_raw: dict, customers: list[dict]) -> dict:
    seg = parse_segment(segment_raw)  # trust boundary; raises SegmentError
    now = datetime.now(timezone.utc)
    matched = evaluate_segment(seg, customers, now=now)
    sample = [
        {"name": c["name"], "email": c["email"], "city": c["city"],
         "lifecycle_stage": c["lifecycle_stage"]}
        for c in matched[:8]
    ]
    return {"count": len(matched), "total": len(customers), "sample": sample}


@router.post("/copilot/propose")
async def propose(
    req: CopilotRequest,
    copilot: Copilot = Depends(copilot_dep),
    repo: Repo = Depends(repo_dep),
) -> dict:
    proposal = await copilot.propose(req.goal)
    customers = [customer_eval_dict(c) for c in await repo.list_customers()]
    preview = _preview(proposal.segment_raw, customers)
    return {**proposal.to_dict(), "preview": preview}


@router.post("/segments/preview")
async def segment_preview(
    req: SegmentPreviewRequest,
    repo: Repo = Depends(repo_dep),
) -> dict:
    customers = [customer_eval_dict(c) for c in await repo.list_customers()]
    try:
        return _preview(req.segment, customers)
    except SegmentError as exc:
        raise HTTPException(status_code=422, detail=f"invalid segment: {exc}")
