import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.catalog import ProductOut


def _money(v: Decimal | None) -> str | None:
    return None if v is None else f"{v:.2f}"


class ScoreComponent(BaseModel):
    key: str  # quality | value | price | durability | fit
    value: int  # 0-100
    weight: float  # 0-1
    contribution: float  # value * weight
    reason: str


class RankedProduct(BaseModel):
    product: ProductOut
    score: float  # 0-100
    rank: int  # within its need
    components: list[ScoreComponent]


class ExcludedProduct(BaseModel):
    product: ProductOut
    reasons: list[str]


class RankingResponse(BaseModel):
    weights: dict[str, float]
    ranked: list[RankedProduct]
    excluded: list[ExcludedProduct]


# ---- Budget ----


class BudgetEvaluation(BaseModel):
    budget_name: str
    limit: Decimal
    committed: Decimal
    proposed: Decimal
    remaining_after: Decimal
    within_budget: bool
    used_pct: int
    currency: str = "USD"
    explanation: str

    @field_serializer("limit", "committed", "proposed", "remaining_after")
    def _m(self, v: Decimal) -> str:
        return _money(v)


# ---- Cart ----


class NeedIn(BaseModel):
    need: str = Field(min_length=1, max_length=48)
    required: bool = True
    quantity: int = Field(1, ge=1, le=10)


class CartRequest(BaseModel):
    budget: Decimal = Field(gt=0, le=Decimal("100000000"), max_digits=12, decimal_places=2)  # user's currency
    needs: list[NeedIn] = Field(min_length=1, max_length=25)
    budget_name: str | None = None  # evaluate the result against this saved budget


class CartLine(BaseModel):
    need: str
    product: ProductOut
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    score: float
    reason: str

    @field_serializer("unit_price", "line_total")
    def _m(self, v: Decimal) -> str:
        return _money(v)


class MerchantShipping(BaseModel):
    merchant: str
    subtotal: Decimal
    shipping: Decimal
    note: str

    @field_serializer("subtotal", "shipping")
    def _m(self, v: Decimal) -> str:
        return _money(v)


class SkippedNeed(BaseModel):
    need: str
    reason: str


class CartPlan(BaseModel):
    feasible: bool
    message: str
    lines: list[CartLine]
    skipped: list[SkippedNeed]
    shipping: list[MerchantShipping]
    subtotal: Decimal
    shipping_total: Decimal
    tax: Decimal
    total: Decimal
    budget: Decimal
    remaining: Decimal
    currency: str = "USD"
    budget_evaluation: BudgetEvaluation | None = None
    tax_note: str = "Tax is not included. It is shown at checkout."

    @field_serializer("subtotal", "shipping_total", "tax", "total", "budget", "remaining")
    def _m(self, v: Decimal) -> str:
        return _money(v)


class NeedOption(BaseModel):
    need: str
    category: str
    count: int


ProductId = uuid.UUID
