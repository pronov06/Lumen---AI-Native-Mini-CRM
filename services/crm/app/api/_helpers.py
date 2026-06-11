"""Small mapping helpers shared by the campaign/segment routes.

Kept in one place so segment evaluation and recipient resolution behave
identically everywhere (preview, create, approve).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.infra import models


def _aware(ts: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on round-trip; treat naive stored times as UTC so
    days_since_* math never mixes aware/naive datetimes."""
    if ts is None:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def customer_eval_dict(c: models.Customer) -> dict:
    """Project a Customer row into the plain dict the Segment evaluator reads
    (FIELDS keys + the two raw timestamps the derived fields are computed from)."""
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "city": c.city,
        "lifecycle_stage": c.lifecycle_stage,
        "channel_optin": c.channel_optin,
        "total_orders": c.total_orders,
        "total_spend": c.total_spend,
        "avg_order_value": c.avg_order_value,
        "last_order_at": _aware(c.last_order_at),
        "signup_at": _aware(c.signup_at),
    }


def recipient_for(channel: str, c: models.Customer) -> str:
    """Pick the contact address the chosen channel would actually use."""
    if channel == "email":
        return c.email
    return c.phone or c.email
