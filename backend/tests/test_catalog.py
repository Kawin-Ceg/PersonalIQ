from decimal import Decimal

from sqlalchemy import func, select

from app.models import Product
from app.seed.catalog import PRODUCTS
from app.seed.run import seed


def test_seed_is_idempotent_and_prices_are_decimal(session):
    seed(session)  # second run must not duplicate
    assert session.scalar(select(func.count()).select_from(Product)) == len(PRODUCTS)
    chair = session.scalar(select(Product).where(Product.sku == "FUR-014"))
    assert chair.price == Decimal("149.99")


def test_products_filter_by_category_and_money_as_string(client):
    body = client.get("/api/v1/products", params={"category": "Kitchen"}).json()
    assert body["total"] > 0
    assert {p["category"] for p in body["items"]} == {"Kitchen"}
    assert isinstance(body["items"][0]["price"], str)
    assert body["is_demo"] is True
