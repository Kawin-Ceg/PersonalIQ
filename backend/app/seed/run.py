"""Load the demo catalog and users. Safe to run repeatedly (upserts by sku / slug / email).

Usage: python -m app.seed.run
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Feedback, Merchant, Product, Transaction, User
from app.schemas.personal import FeedbackIn, OnboardingIn
from app.seed.catalog import MERCHANTS, PRODUCTS, USERS
from app.services import personal_intelligence as pi


def seed(session: Session) -> dict[str, int]:
    merchants: dict[str, Merchant] = {}
    for m in MERCHANTS:
        row = session.scalar(select(Merchant).where(Merchant.slug == m["slug"])) or Merchant(slug=m["slug"])
        row.name = m["name"]
        row.shipping_flat = Decimal(m["shipping_flat"])
        row.free_shipping_over = Decimal(m["free_shipping_over"]) if m["free_shipping_over"] else None
        row.return_window_days = m["return_window_days"]
        row.currency = "USD"
        session.add(row)
        merchants[m["slug"]] = row
    session.flush()

    for p in PRODUCTS:
        row = session.scalar(select(Product).where(Product.sku == p["sku"])) or Product(sku=p["sku"])
        row.merchant_id = merchants[p["merchant"]].id
        row.name = p["name"]
        row.category = p["category"]
        row.description = p["description"]
        row.price = Decimal(p["price"])
        row.currency = "USD"
        row.quality_score = p["quality_score"]
        row.durability_score = p["durability_score"]
        row.rating = p["rating"]
        row.review_count = p["review_count"]
        row.warranty_months = p["warranty_months"]
        row.availability = "in_stock"
        row.attributes = p["attributes"]
        session.add(row)

    for u in USERS:
        user = session.scalar(select(User).where(User.email == u["email"]))
        if user is None:
            user = User(email=u["email"])
            session.add(user)
        user.name = u["name"]
        user.timezone = u["timezone"]
        user.currency = u["currency"]
        session.flush()
        for b in u["budgets"]:
            budget = session.scalar(select(Budget).where(Budget.user_id == user.id, Budget.name == b["name"]))
            if budget is None:
                budget = Budget(user_id=user.id, name=b["name"])
                session.add(budget)
            budget.period = b["period"]
            budget.limit_amount = Decimal(b["limit_amount"])
            budget.currency = user.currency

    session.commit()

    for u in USERS:
        user = session.scalar(select(User).where(User.email == u["email"]))
        _seed_history(session, user, u)

    return {"merchants": len(MERCHANTS), "products": len(PRODUCTS), "users": len(USERS)}


def _seed_history(session: Session, user: User, u: dict) -> None:
    """Give a demo user onboarding answers, spending and feedback, through the same engine the app uses."""
    if u.get("onboarding"):
        pi.apply_onboarding(session, user, OnboardingIn(**u["onboarding"]))

    has_tx = session.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id))
    if u.get("transactions") and not has_tx:
        today = date.today()
        lines = ["date,merchant,category,amount"] + [
            f"{today - timedelta(days=d)},{m},{c},{a}" for d, m, c, a in u["transactions"]
        ]
        pi.import_transactions_csv(session, user, "\n".join(lines))

    has_fb = session.scalar(select(func.count()).select_from(Feedback).where(Feedback.user_id == user.id))
    if u.get("feedback") and not has_fb:
        for f in u["feedback"]:
            product = session.scalar(select(Product).where(Product.sku == f["sku"]))
            pi.record_feedback(
                session, user,
                FeedbackIn(product_id=product.id, rating=f["rating"], worked=f.get("worked", ""),
                           didnt_work=f.get("didnt_work", ""), reasons=f.get("reasons", [])),
            )


if __name__ == "__main__":
    from app.core.database import new_session

    with new_session() as s:
        print(seed(s))
