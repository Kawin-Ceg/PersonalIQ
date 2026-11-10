import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, JsonB, TimestampMixin, currency_column, money_column


class Workflow(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflows"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    objective_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("objectives.id"), nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(32), default="running")
    state: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)


class AgentRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    agent_name: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(24), default="running")  # running | completed | needs_input | failed
    input: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    # Set in Python (not by the DB) so durations are precise to the millisecond.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(IdMixin, TimestampMixin, Base):
    """Authorises one exact order version. order_hash covers items, amounts, currency and merchant."""

    __tablename__ = "approvals"

    workflow_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("workflows.id"), nullable=True)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    order_version: Mapped[int] = mapped_column(Integer)
    order_hash: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(32), default="purchase")
    # pending | approved | rejected | expired | superseded (the order changed, a new approval replaced it)
    # | invalidated (approved, but the order or its prices changed before payment)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # {"risk": {...per item and order...}, "confirmed": {item_id: "kept"|"swapped"}, "budget": {...}}
    details: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)


class Payment(IdMixin, TimestampMixin, Base):
    """One PayPal order for one approved order version. amount/currency are what PayPal is asked to charge."""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("provider", "provider_order_id"), UniqueConstraint("order_id", "attempt", name="uq_payments_order_attempt"))

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id"), index=True)
    approval_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("approvals.id"))
    # 1, 2, 3... per order. Unique, so two simultaneous "create" clicks can't both start a PayPal order.
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(24), default="paypal")
    provider_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # creating | created | capturing | completed | pending | unknown | failed | replaced | cancelled
    status: Mapped[str] = mapped_column(String(32), default="creating")
    amount: Mapped[Decimal] = money_column()
    currency: Mapped[str] = currency_column()
    # PayPal-Request-Id for the create call; the capture uses "<this>-capture". Retries reuse them.
    request_id: Mapped[str] = mapped_column(String(80), unique=True)
    paypal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)  # PayPal's order status
    capture_status: Mapped[str | None] = mapped_column(String(32), nullable=True)  # PayPal's capture status
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    # Set only when PayPal's own response confirmed a COMPLETED capture with the right amount and currency.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentEvent(IdMixin, TimestampMixin, Base):
    """Every provider event, stored once (unique event id makes webhook handling idempotent)."""

    __tablename__ = "payment_events"

    payment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payments.id"), nullable=True)
    provider_event_id: Mapped[str] = mapped_column(String(80), unique=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)


class AuditLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(48))  # user | system | agent:<name>
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    # Python-side time so events written in the same second keep their order on the timeline.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
