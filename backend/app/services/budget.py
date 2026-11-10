"""Budget arithmetic. Decimal only; the LLM never does this math."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Order
from app.services.fx import fmt

CENT = Decimal("0.01")
# Money already gone (verified payment) vs money promised (approved, payment not finished yet).
SPENT_STATUSES = ("paid",)
IN_FLIGHT_STATUSES = ("approved", "paypal_order_created", "awaiting_buyer_checkout", "capturing", "reconciliation_required")
COMMITTED_STATUSES = SPENT_STATUSES + IN_FLIGHT_STATUSES


def evaluate(name: str, limit: Decimal, committed: Decimal, proposed: Decimal, currency: str = "USD") -> dict:
    remaining = (limit - committed - proposed).quantize(CENT, ROUND_HALF_UP)
    used = committed + proposed
    used_pct = int((used / limit * 100).quantize(Decimal(1), ROUND_HALF_UP)) if limit > 0 else 100
    within = remaining >= 0
    if within:
        explanation = f"{fmt(proposed, currency)} fits. {fmt(remaining, currency)} of your {fmt(limit, currency)} {name} budget would be left."
    else:
        explanation = f"{fmt(proposed, currency)} is {fmt(-remaining, currency)} over what's left of your {fmt(limit, currency)} {name} budget."
    return {
        "budget_name": name,
        "limit": limit,
        "committed": committed,
        "proposed": proposed,
        "remaining_after": remaining,
        "within_budget": within,
        "used_pct": used_pct,
        "currency": currency,
        "explanation": explanation,
    }


def budget_usage(session: Session, user_id: uuid.UUID, budget: Budget, today: date | None = None) -> dict[str, Decimal]:
    """Orders planned against THIS budget: spent (paid) and in flight (approved, payment not finished).
    Monthly budgets only count orders from the current month."""

    def total(statuses: tuple[str, ...]) -> Decimal:
        stmt = select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.user_id == user_id, Order.budget_id == budget.id, Order.status.in_(statuses), Order.currency == budget.currency
        )
        if budget.period == "monthly":
            t = today or date.today()
            stmt = stmt.where(Order.created_at >= date(t.year, t.month, 1))
        return Decimal(session.scalar(stmt)).quantize(CENT)

    return {"spent": total(SPENT_STATUSES), "in_flight": total(IN_FLIGHT_STATUSES)}


def committed_amount(session: Session, user_id: uuid.UUID, budget: Budget, today: date | None = None) -> Decimal:
    """Everything already taken out of a budget: spent plus in flight."""
    u = budget_usage(session, user_id, budget, today)
    return u["spent"] + u["in_flight"]


DUPLICATE_WINDOW_DAYS = 90


def recently_bought_needs(session: Session, user_id: uuid.UUID) -> set[str]:
    """Needs the user already paid for in the last 90 days (duplicate-purchase check)."""
    from datetime import datetime, timedelta, timezone

    from app.models import OrderItem, Product
    from app.services.ranking import need_of

    since = datetime.now(timezone.utc) - timedelta(days=DUPLICATE_WINDOW_DAYS)
    rows = session.scalars(
        select(Product)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user_id, Order.status.in_(("paid", "completed")), Order.created_at >= since)
    )
    return {need_of(p) for p in rows}


# A request with no amount uses the saved budget that matches it, else the monthly one.
TEMPLATE_BUDGET = {"apartment": "Apartment move"}


def resolve_budget(session: Session, user_id: uuid.UUID, template: str | None) -> Budget | None:
    budgets = {b.name: b for b in session.scalars(select(Budget).where(Budget.user_id == user_id))}
    return budgets.get(TEMPLATE_BUDGET.get(template or "", "")) or budgets.get("Monthly discretionary")


def evaluate_saved_budget(session: Session, user_id: uuid.UUID, name: str, proposed: Decimal) -> dict | None:
    budget = session.scalar(select(Budget).where(Budget.user_id == user_id, Budget.name == name))
    if budget is None:
        return None
    return evaluate(budget.name, budget.limit_amount, committed_amount(session, user_id, budget), proposed, budget.currency)
