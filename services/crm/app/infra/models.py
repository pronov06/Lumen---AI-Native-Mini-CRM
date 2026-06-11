"""Persistence schema (SQLAlchemy 2.0 async, works on Postgres and SQLite).

The shape mirrors the domain:
  - customer / order        : the ingested CRM data segmentation runs over
  - campaign / communication: a send and its per-recipient fan-out
  - communication_event     : the append-only log; the comm row is a *cache* of
                              the projection over its events, updated on ingest

The uniqueness constraint on communication_event is the idempotency guarantee:
re-ingesting the same (communication_id, event_type, provider_event_id) violates
it and is treated as a no-op.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    channel_optin: Mapped[str] = mapped_column(String, default="email")
    lifecycle_stage: Mapped[str] = mapped_column(String, default="new")
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_spend: Mapped[int] = mapped_column(Integer, default=0)  # minor units
    avg_order_value: Mapped[int] = mapped_column(Integer, default=0)
    signup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[int] = mapped_column(Integer)  # minor units
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Set when an order is attributed to a campaign communication (post-click).
    attributed_communication_id: Mapped[str | None] = mapped_column(String, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="orders")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    segment_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # draft -> approved -> sending -> sent  (HITL gate sits between draft/approved)
    status: Mapped[str] = mapped_column(String, default="draft")
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Communication(Base):
    """One message to one recipient. `state` and the *_at columns are a cached
    projection over communication_event rows, recomputed on every ingest."""

    __tablename__ = "communications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String)
    recipient: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="queued", index=True)
    failed: Mapped[bool] = mapped_column(default=False)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # Denormalized lifecycle timestamps (from the projection) for fast funnels.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommunicationEvent(Base):
    """Immutable callback fact. The unique constraint *is* the idempotency key."""

    __tablename__ = "communication_events"
    __table_args__ = (
        UniqueConstraint(
            "communication_id", "event_type", "provider_event_id",
            name="uq_comm_event_idem",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    communication_id: Mapped[str] = mapped_column(
        ForeignKey("communications.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String)
    provider_event_id: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class DeadLetter(Base):
    """Where a callback or send goes after exhausting retries — never silently
    dropped, always surfaceable in the UI."""

    __tablename__ = "dead_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)  # "send" | "callback"
    payload: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
