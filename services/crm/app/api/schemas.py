"""API schemas. Kept separate from the ORM models so the wire contract and the
storage schema can evolve independently."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeedRequest(BaseModel):
    n_customers: int = Field(default=240, ge=1, le=5000)
    seed: int = 7


class CopilotRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)


class SegmentPreviewRequest(BaseModel):
    segment: dict


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    segment: dict
    channel: str
    message: str = Field(min_length=1, max_length=1000)


class CampaignOut(BaseModel):
    id: str
    name: str
    channel: str
    message: str
    status: str
    recipient_count: int
    segment: dict


class ReceiptIn(BaseModel):
    communication_id: str
    event_type: str
    provider_event_id: str
    channel: str | None = None
    recipient: str | None = None
    meta: dict = Field(default_factory=dict)
