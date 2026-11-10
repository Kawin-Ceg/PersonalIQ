"""Shared column types and mixins."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# JSONB on Postgres, plain JSON elsewhere (lets tests run on SQLite).
JsonB = JSON().with_variant(JSONB(), "postgresql")

# Money is always NUMERIC(18,2) + an ISO 4217 code. Never float.
Money = Numeric(18, 2, asdecimal=True)


def money_column() -> Mapped[Decimal]:
    return mapped_column(Money, nullable=False)


def currency_column() -> Mapped[str]:
    return mapped_column(String(3), nullable=False, default="USD")


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
