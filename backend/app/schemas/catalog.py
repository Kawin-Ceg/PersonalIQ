import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class MerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    return_window_days: int


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    category: str
    description: str
    price: Decimal
    currency: str
    quality_score: int
    durability_score: int
    rating: float
    review_count: int
    availability: str
    warranty_months: int
    attributes: dict
    merchant: MerchantOut
    # When `price` is converted to the user's currency, the original catalog price is kept here.
    base_price: Decimal | None = None
    base_currency: str | None = None

    # Money goes over the wire as a string ("149.99") so no client ever sees a float.
    @field_serializer("price", "base_price")
    def _price(self, v: Decimal | None) -> str | None:
        return None if v is None else f"{v:.2f}"


def product_out(p, currency: str) -> "ProductOut":
    """Product as the user sees it: price converted to their currency, catalog price kept alongside."""
    from app.services.fx import convert

    out = ProductOut.model_validate(p)
    return out.model_copy(
        update={"price": convert(p.price, p.currency, currency), "currency": currency, "base_price": p.price, "base_currency": p.currency}
    )


class CategoryCount(BaseModel):
    category: str
    count: int


class CatalogResponse(BaseModel):
    items: list[ProductOut]
    total: int
    categories: list[CategoryCount]
    is_demo: bool = True
