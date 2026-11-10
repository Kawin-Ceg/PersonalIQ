"""Demo product catalog search. Ranking score arrives in feature 2."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Product


def search_products(session: Session, category: str | None = None, q: str | None = None) -> list[Product]:
    stmt = select(Product).order_by(Product.category, Product.name)
    if category:
        stmt = stmt.where(Product.category == category)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like)))
    return list(session.scalars(stmt).unique())


def category_counts(session: Session) -> list[tuple[str, int]]:
    stmt = select(Product.category, func.count()).group_by(Product.category).order_by(Product.category)
    return [(c, n) for c, n in session.execute(stmt)]
