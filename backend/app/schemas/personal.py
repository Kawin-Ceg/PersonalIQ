import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

Dimension = Literal["durability", "quality", "price", "value"]
Level = Literal["high", "medium", "low"]
Source = Literal["user_stated", "uploaded", "feedback", "observed", "inferred"]
# What a buyer can rate after using something. "price" isn't an aspect: you rate value for money.
Aspect = Literal["quality", "durability", "value"]


class OnboardingIn(BaseModel):
    priorities: list[Dimension] = Field(default_factory=list, max_length=2)
    price_sensitivity: Level = "medium"
    avoid_materials: list[str] = Field(default_factory=list, max_length=20)
    like_merchants: list[str] = Field(default_factory=list)  # merchant slugs
    avoid_merchants: list[str] = Field(default_factory=list)
    likes: list[str] = Field(default_factory=list, max_length=10)  # free text, e.g. "minimal design"
    dislikes: list[str] = Field(default_factory=list, max_length=10)
    monthly_budget: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_type: str
    content: str
    source: str
    confidence: float
    created_at: datetime
    updated_at: datetime
    meta: dict


class MemoryPatch(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=500)
    level: Level | None = None


class FeedbackIn(BaseModel):
    product_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None  # set when rating something bought through PersonalIQ
    item_name: str | None = Field(None, max_length=200)
    rating: int = Field(ge=1, le=10)
    worked: str = Field("", max_length=1000)
    didnt_work: str = Field("", max_length=1000)
    reasons: list[Dimension] = Field(default_factory=list)
    aspects: dict[Aspect, int] = Field(default_factory=dict)  # 1-10 each, optional

    @field_validator("aspects")
    @classmethod
    def _aspect_range(cls, v: dict[str, int]) -> dict[str, int]:
        if any(not 1 <= x <= 10 for x in v.values()):
            raise ValueError("aspect scores must be 1-10")
        return v


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_name: str
    rating: int
    worked: str
    didnt_work: str
    reasons: list[str]
    aspects: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    # Only on the response to a new rating: what changed because of it.
    learning: dict | None = None


class EventIn(BaseModel):
    event_type: Literal["product_view", "compare", "recommendation_accepted", "recommendation_rejected"]
    product_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)


class CsvImportIn(BaseModel):
    csv: str = Field(max_length=500_000)


class CsvImportOut(BaseModel):
    imported: int
    duplicates: int
    errors: list[str]


# ---- User context: the structured profile agents receive ----


class Signal(BaseModel):
    level: Level
    source: Source | Literal["default"]
    reason: str


class CategorySpend(BaseModel):
    category: str
    total: Decimal
    share_pct: int

    @field_serializer("total")
    def _t(self, v: Decimal) -> str:
        return f"{v:.2f}"


class SpendingSummary(BaseModel):
    window_days: int
    currency: str
    total: Decimal
    monthly_average: Decimal
    transaction_count: int
    by_category: list[CategorySpend]
    top_merchants: list[str]

    @field_serializer("total", "monthly_average")
    def _m(self, v: Decimal) -> str:
        return f"{v:.2f}"


class BudgetOut(BaseModel):
    name: str
    period: str
    limit_amount: Decimal
    currency: str

    @field_serializer("limit_amount")
    def _l(self, v: Decimal) -> str:
        return f"{v:.2f}"


class UserContext(BaseModel):
    user_id: uuid.UUID
    name: str
    currency: str  # home currency; all money in this context is in it
    onboarded: bool
    budgets: list[BudgetOut]
    importance: dict[str, Signal]
    price_sensitivity: Signal
    avoid_materials: list[str]
    like_merchants: list[str]
    avoid_merchants: list[str]
    likes: list[str]
    dislikes: list[str]
    lessons: list[str]
    recent_interest: list[str]
    spending: SpendingSummary | None
    # Weights for the ranking formula Score = wQ*Q + wV*V + wP*P + wR*R + wF*F (sum = 1.0)
    scoring_weights: dict[str, float]
    # Learned from aspect ratings: weights for one category, e.g. Furniture leans harder on durability.
    category_weights: dict[str, dict[str, float]] = Field(default_factory=dict)
    category_importance: dict[str, dict[str, Signal]] = Field(default_factory=dict)
    memory_count: int


class DemoUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    currency: str
    onboarded_at: datetime | None
