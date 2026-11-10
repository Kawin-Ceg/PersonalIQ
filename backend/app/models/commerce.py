import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, JsonB, Money, TimestampMixin, currency_column, money_column


class Merchant(IdMixin, TimestampMixin, Base):
    __tablename__ = "merchants"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    return_window_days: Mapped[int] = mapped_column(Integer, default=30)
    shipping_flat: Mapped[Decimal] = money_column()
    free_shipping_over: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    currency: Mapped[str] = currency_column()


class Product(IdMixin, TimestampMixin, Base):
    """Demo catalog item. Scores are curated 0-100 values, not live data."""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(64), unique=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = money_column()
    currency: Mapped[str] = currency_column()
    quality_score: Mapped[int] = mapped_column(Integer)
    durability_score: Mapped[int] = mapped_column(Integer)
    rating: Mapped[float] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    availability: Mapped[str] = mapped_column(String(24), default="in_stock")
    warranty_months: Mapped[int] = mapped_column(Integer, default=12)
    # {"materials": [...], "tags": [...], "essential_for": ["apartment"]}
    attributes: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)

    merchant: Mapped[Merchant] = relationship(lazy="joined")


class Objective(IdMixin, TimestampMixin, Base):
    __tablename__ = "objectives"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="planning")
    budget_limit: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    currency: Mapped[str] = currency_column()
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)


class Task(IdMixin, TimestampMixin, Base):
    """One step of an objective's plan. `tracking` says who marks it done:
    auto = PersonalIQ, from real events (approval, payment, ratings); manual = you."""

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("objective_id", "key"),)

    objective_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("objectives.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(32))  # you | life_operations | consumer_buyer | procurement | financial | post_purchase
    tracking: Mapped[str] = mapped_column(String(8), default="auto")  # auto | manual
    external: Mapped[bool] = mapped_column(default=False)  # needs a service PersonalIQ can't book
    depends_on: Mapped[list[str]] = mapped_column(JsonB, default=list)  # keys of other tasks
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="todo")  # todo | done
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Order(IdMixin, TimestampMixin, Base):
    """A proposed or confirmed order. `version` bumps on any change so old approvals stop applying."""

    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    objective_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("objectives.id"), nullable=True)
    # The saved budget this order was planned against; it counts only against that one.
    budget_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("budgets.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    subtotal: Mapped[Decimal] = money_column()
    shipping: Mapped[Decimal] = money_column()
    tax: Mapped[Decimal] = money_column()
    total: Mapped[Decimal] = money_column()
    currency: Mapped[str] = currency_column()

    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(IdMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = money_column()
    line_total: Mapped[Decimal] = money_column()
    reason: Mapped[str] = mapped_column(Text, default="")
