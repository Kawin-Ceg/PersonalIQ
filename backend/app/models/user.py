import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, JsonB, TimestampMixin, currency_column, money_column


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # Home currency: every amount the user sees and every budget they set is in this currency.
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    # Raw onboarding answers. The source of truth for learned facts is the memories table.
    preferences: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Budget(IdMixin, TimestampMixin, Base):
    __tablename__ = "budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    period: Mapped[str] = mapped_column(String(16), default="monthly")  # monthly | one_off
    limit_amount: Mapped[Decimal] = money_column()
    currency: Mapped[str] = currency_column()
    is_hard_limit: Mapped[bool] = mapped_column(default=True)
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class Memory(IdMixin, TimestampMixin, Base):
    """A remembered fact with provenance. AI-inferred memories are never treated as verified."""

    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(32))  # importance | exclusion | merchant | like | dislike | lesson
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="user_stated")  # user_stated | uploaded | feedback | observed | inferred
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JsonB, default=dict)


class Transaction(IdMixin, TimestampMixin, Base):
    """Spending history uploaded by the user (CSV) or recorded by PersonalIQ after a verified payment."""

    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    merchant: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = money_column()
    currency: Mapped[str] = currency_column()
    source: Mapped[str] = mapped_column(String(24), default="uploaded")  # uploaded | paypal (a verified PersonalIQ purchase)
    # Hash of date+merchant+amount+currency so re-uploading the same file adds nothing.
    fingerprint: Mapped[str] = mapped_column(String(64))


class Feedback(IdMixin, TimestampMixin, Base):
    """What worked and what didn't, for something the user bought (through PersonalIQ or before)."""

    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("products.id"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("orders.id"), nullable=True)
    item_name: Mapped[str] = mapped_column(String(200))
    rating: Mapped[int] = mapped_column(Integer)  # 1-10
    worked: Mapped[str] = mapped_column(Text, default="")
    didnt_work: Mapped[str] = mapped_column(Text, default="")
    # Which dimensions this outcome speaks to: durability | quality | price | value
    reasons: Mapped[list[str]] = mapped_column(JsonB, default=list)
    # Per-aspect scores 1-10, e.g. {"durability": 3, "quality": 8}. Optional.
    aspects: Mapped[dict[str, int]] = mapped_column(JsonB, default=dict)


class UserEvent(IdMixin, TimestampMixin, Base):
    """Observed behaviour: product views, comparisons, accepted or rejected recommendations."""

    __tablename__ = "user_events"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("products.id"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    # {"pending": <request waiting for an answer>, "rounds": <questions asked so far>}
    state: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    # assistant messages: {"status", "workflow_id", "suggestions", "understood"}
    meta: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    # Python-side timestamp so messages created in the same request keep their order.
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
