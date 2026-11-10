"""Personal Intelligence Engine.

Turns what PersonalIQ knows about a user (four channels, all stored as memories) into one
structured UserContext that agents receive. Pure, deterministic Python: no LLM here.

Channels:
  1. user_stated  - onboarding answers and corrections
  2. uploaded     - transaction CSV (spending analysis)
  3. observed     - product views, rejected recommendations
  4. feedback     - ratings of past purchases, what worked and what didn't
"""

import csv
import hashlib
import io
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, Feedback, Merchant, Order, Product, Transaction, User, UserEvent
from app.schemas.personal import (
    BudgetOut,
    CategorySpend,
    CsvImportOut,
    FeedbackIn,
    OnboardingIn,
    Signal,
    SpendingSummary,
    UserContext,
)
from app.services.memory import by_key, forget, list_memories, remember

DIMENSIONS = ("quality", "value", "price", "durability")
LABEL = {"quality": "Quality", "value": "Value for money", "price": "Low price", "durability": "Durability"}

# Base weights of the ranking formula. F (preference fit) is fixed at 0.10.
BASE_WEIGHTS = {"quality": 0.30, "value": 0.25, "price": 0.20, "durability": 0.15}
FIT_WEIGHT = 0.10
# "high" is strong enough that your top priority always ends up with the largest weight.
LEVEL_FACTOR = {"high": 2.5, "medium": 1.0, "low": 0.5}
# A category lesson from your own bad experience outweighs a general preference,
# so "high" for one category is stronger than "high" in general.
CATEGORY_HIGH_FACTOR = 4.0

SPEND_WINDOW_DAYS = 90
CENT = Decimal("0.01")


ASPECT_LABEL = {"quality": "quality", "durability": "durability", "value": "value for money"}
POOR_ASPECT = 4  # an aspect scored this low or lower teaches something
CATEGORY_KEY = "importance.{dim}.category.{category}"


def describe_level(key: str, level: str) -> str:
    """Sentence for an importance-type memory, e.g. after the user corrects its level."""
    if key == "price_sensitivity":
        return f"Price sensitivity: {level}."
    dim = key.removeprefix("importance.")
    if ".category." in dim:
        dim, category = dim.split(".category.", 1)
        return f"{LABEL.get(dim, dim)} matters for {category} ({level})."
    return f"{LABEL.get(dim, dim)} matters to you ({level})."


def _category_key(key: str) -> tuple[str, str] | None:
    """'importance.durability.category.Furniture' -> ('durability', 'Furniture')."""
    if not key.startswith("importance.") or ".category." not in key:
        return None
    dim, category = key.removeprefix("importance.").split(".category.", 1)
    return (dim, category) if dim in DIMENSIONS else None


# ---------- Channel 1: onboarding ----------


def apply_onboarding(session: Session, user: User, data: OnboardingIn) -> None:
    uid = user.id
    # Re-submitting onboarding replaces earlier answers, never memories from other sources.
    for prefix in ("importance.", "price_sensitivity", "avoid.", "like.", "dislike."):
        forget(session, uid, prefix)
    session.flush()

    for rank, dim in enumerate(data.priorities):
        level = "high" if rank == 0 else "medium"
        remember(session, uid, f"importance.{dim}", describe_level(f"importance.{dim}", level), "importance", "user_stated", level=level)
    remember(
        session, uid, "price_sensitivity", f"Price sensitivity: {data.price_sensitivity}.", "importance", "user_stated",
        level=data.price_sensitivity,
    )
    for m in {x.strip().lower() for x in data.avoid_materials if x.strip()}:
        remember(session, uid, f"avoid.material.{m}", f"Avoid products made with {m}.", "exclusion", "user_stated", value=m)

    merchants = {m.slug: m.name for m in session.scalars(select(Merchant))}
    for slug in data.like_merchants:
        if slug in merchants:
            remember(session, uid, f"like.merchant.{slug}", f"You like shopping at {merchants[slug]}.", "merchant", "user_stated", value=slug)
    for slug in data.avoid_merchants:
        if slug in merchants:
            remember(session, uid, f"avoid.merchant.{slug}", f"Avoid {merchants[slug]}.", "merchant", "user_stated", value=slug)
    for i, text in enumerate(t.strip() for t in data.likes if t.strip()):
        remember(session, uid, f"like.text.{i}", f"Likes: {text}", "like", "user_stated", value=text)
    for i, text in enumerate(t.strip() for t in data.dislikes if t.strip()):
        remember(session, uid, f"dislike.text.{i}", f"Dislikes: {text}", "dislike", "user_stated", value=text)

    if data.monthly_budget is not None:
        budget = session.scalar(select(Budget).where(Budget.user_id == uid, Budget.name == "Monthly discretionary"))
        if budget is None:
            budget = Budget(user_id=uid, name="Monthly discretionary", period="monthly")
            session.add(budget)
        budget.limit_amount = data.monthly_budget.quantize(CENT)
        budget.currency = user.currency

    user.preferences = data.model_dump(mode="json")
    user.onboarded_at = datetime.now(timezone.utc)
    session.commit()


# ---------- Channel 2: uploaded transactions ----------


def import_transactions_csv(session: Session, user: User, text: str) -> CsvImportOut:
    """CSV columns: date (YYYY-MM-DD), merchant, category, amount, optional currency (default: the user's)."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    required = {"date", "merchant", "category", "amount"}
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    if not required <= headers:
        return CsvImportOut(imported=0, duplicates=0, errors=[f"Missing columns: {', '.join(sorted(required - headers))}"])

    existing = set(session.scalars(select(Transaction.fingerprint).where(Transaction.user_id == user.id)))
    imported, duplicates, errors = 0, 0, []
    for line, raw in enumerate(reader, start=2):
        if None in raw:  # extra fields, usually an unquoted "1,234.50" that would otherwise import as 1
            errors.append(f"Line {line}: too many columns (put quotes around amounts with commas)")
            continue
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            occurred = date.fromisoformat(row["date"])
            amount = Decimal(row["amount"].replace(",", "")).quantize(CENT, ROUND_HALF_UP)
        except (ValueError, InvalidOperation):
            errors.append(f"Line {line}: bad date or amount")
            continue
        if amount <= 0 or not row["merchant"]:
            errors.append(f"Line {line}: amount must be positive and merchant set")
            continue
        currency = (row.get("currency") or user.currency).upper()[:3]
        fp = hashlib.sha256(f"{occurred}|{row['merchant'].lower()}|{amount}|{currency}".encode()).hexdigest()
        if fp in existing:
            duplicates += 1
            continue
        existing.add(fp)
        session.add(
            Transaction(
                user_id=user.id, occurred_on=occurred, merchant=row["merchant"], category=row["category"] or "Other",
                amount=amount, currency=currency, source="uploaded", fingerprint=fp,
            )
        )
        imported += 1
    session.commit()
    return CsvImportOut(imported=imported, duplicates=duplicates, errors=errors[:20])


def spending_summary(session: Session, user_id: uuid.UUID, currency: str, today: date | None = None) -> SpendingSummary | None:
    """Spending in the user's home currency over the last 90 days."""
    today = today or date.today()
    since = today - timedelta(days=SPEND_WINDOW_DAYS)
    rows = list(
        session.scalars(
            select(Transaction).where(Transaction.user_id == user_id, Transaction.occurred_on >= since, Transaction.currency == currency)
        )
    )
    if not rows:
        return None
    total = sum((r.amount for r in rows), Decimal("0"))
    by_cat: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        by_cat[r.category] += r.amount
    merchants = Counter(r.merchant for r in rows)
    return SpendingSummary(
        window_days=SPEND_WINDOW_DAYS,
        currency=currency,
        total=total,
        monthly_average=(total / Decimal(SPEND_WINDOW_DAYS) * Decimal(30)).quantize(CENT, ROUND_HALF_UP),
        transaction_count=len(rows),
        by_category=[
            CategorySpend(category=c, total=t, share_pct=int((t / total * 100).quantize(Decimal(1), ROUND_HALF_UP)))
            for c, t in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
        ],
        top_merchants=[m for m, _ in merchants.most_common(3)],
    )


# ---------- Channel 3: observed behaviour ----------


def record_event(session: Session, user: User, event_type: str, product_id: uuid.UUID | None, payload: dict) -> None:
    session.add(UserEvent(user_id=user.id, event_type=event_type, product_id=product_id, payload=payload))
    session.flush()
    _learn_from_behaviour(session, user.id)
    session.commit()


def _learn_from_behaviour(session: Session, user_id: uuid.UUID) -> None:
    """Two recommendations rejected as too expensive means price matters more than we assumed."""
    rejected = session.scalars(
        select(UserEvent).where(UserEvent.user_id == user_id, UserEvent.event_type == "recommendation_rejected")
    )
    too_expensive = sum(1 for e in rejected if e.payload.get("reason") == "too_expensive")
    if too_expensive >= 2:
        remember(
            session, user_id, "price_sensitivity",
            f"You turned down {too_expensive} recommendations as too expensive.", "importance", "observed", level="high",
        )


def recent_interest(session: Session, user_id: uuid.UUID, days: int = 30) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(Product.category)
        .join(UserEvent, UserEvent.product_id == Product.id)
        .where(UserEvent.user_id == user_id, UserEvent.event_type == "product_view", UserEvent.created_at >= since)
    )
    return [c for c, _ in Counter(session.scalars(stmt)).most_common(3)]


# ---------- Channel 4: feedback and outcomes ----------


class FeedbackError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def record_feedback(session: Session, user: User, data: FeedbackIn) -> Feedback:
    product = session.get(Product, data.product_id) if data.product_id else None
    if data.order_id:
        # Feedback on a PersonalIQ purchase: your paid order, an item in it, rated once.
        order = session.get(Order, data.order_id)
        if order is None or order.user_id != user.id:
            raise FeedbackError(404, "Order not found.")
        if order.status != "paid":
            raise FeedbackError(409, "You can rate items once the order is paid.")
        if product is None or all(i.product_id != product.id for i in order.items):
            raise FeedbackError(422, "That product isn't in this order.")
        if session.scalar(select(Feedback.id).where(Feedback.order_id == order.id, Feedback.product_id == product.id)):
            raise FeedbackError(409, "You already rated this item.")
    name = product.name if product else (data.item_name or "Unnamed item")
    fb = Feedback(
        user_id=user.id, product_id=product.id if product else None, order_id=data.order_id, item_name=name, rating=data.rating,
        worked=data.worked.strip(), didnt_work=data.didnt_work.strip(), reasons=list(dict.fromkeys(data.reasons)),
        aspects=dict(data.aspects),
    )
    session.add(fb)
    session.flush()

    # A poor aspect is a lesson about this KIND of product, not everything you buy:
    # durability 3/10 on a bed frame makes durability weigh more for Furniture only.
    if product is not None:
        for dim, score in fb.aspects.items():
            if score <= POOR_ASPECT:
                remember(
                    session, user.id, CATEGORY_KEY.format(dim=dim, category=product.category),
                    f"{LABEL[dim]} matters more for {product.category}: {name} scored {score}/10 on {ASPECT_LABEL[dim]}.",
                    "importance", "feedback", level="high", category=product.category, dimension=dim, feedback_id=str(fb.id),
                )

    detail = f" ({fb.didnt_work})" if fb.didnt_work else ""
    if fb.rating <= 5:
        remember(session, user.id, f"lesson.{fb.id}", f"{name}: {fb.rating}/10{detail}.", "lesson", "feedback", rating=fb.rating)
        # A disappointing outcome makes the dimensions it failed on matter more next time.
        for dim in fb.reasons:
            remember(
                session, user.id, f"importance.{dim}",
                f"{LABEL[dim]} matters more: {name} rated {fb.rating}/10{detail}.", "importance", "feedback", level="high",
            )
    elif fb.rating >= 8:
        good = f" ({fb.worked})" if fb.worked else ""
        remember(session, user.id, f"lesson.{fb.id}", f"{name}: {fb.rating}/10, worked well{good}.", "lesson", "feedback", rating=fb.rating)
    session.commit()
    return fb


# ---------- The combined context ----------


def scoring_weights(importance: dict[str, Signal], category_dims: frozenset[str] = frozenset()) -> dict[str, float]:
    """Scale the base weights by how much each dimension matters, keep their sum at 0.90, F stays 0.10.
    `category_dims` are dimensions set by a category lesson; "high" there uses the stronger factor."""

    def factor(d: str) -> float:
        level = importance[d].level
        return CATEGORY_HIGH_FACTOR if d in category_dims and level == "high" else LEVEL_FACTOR[level]

    raw = {d: BASE_WEIGHTS[d] * factor(d) for d in DIMENSIONS}
    scale = (1 - FIT_WEIGHT) / sum(raw.values())
    weights = {d: round(w * scale, 3) for d, w in raw.items()}
    weights["fit"] = FIT_WEIGHT
    return weights


def build_user_context(session: Session, user: User) -> UserContext:
    memories = list_memories(session, user.id)
    keyed = by_key(memories)

    def signal(key: str) -> Signal:
        m = keyed.get(key)
        if m is None:
            return Signal(level="medium", source="default", reason="No information yet.")
        return Signal(level=m.meta.get("level", "medium"), source=m.source, reason=m.content)

    importance = {d: signal(f"importance.{d}") for d in DIMENSIONS}
    price_sens = signal("price_sensitivity")
    # High price sensitivity lifts the price dimension unless the user set price importance directly.
    if price_sens.level == "high" and importance["price"].source in ("default", "observed", "inferred"):
        importance["price"] = Signal(level="high", source=price_sens.source, reason=price_sens.reason)

    # Category lessons override the general level for that category only.
    category_importance: dict[str, dict[str, Signal]] = {}
    for key, m in keyed.items():
        parsed = _category_key(key)
        if parsed:
            dim, category = parsed
            cat = category_importance.setdefault(category, dict(importance))
            cat[dim] = Signal(level=m.meta.get("level", "high"), source=m.source, reason=m.content)

    def values(prefix: str) -> list[str]:
        return [m.meta["value"] for k, m in keyed.items() if k.startswith(prefix) and "value" in m.meta]

    budgets = session.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.name))
    return UserContext(
        user_id=user.id,
        name=user.name,
        currency=user.currency,
        onboarded=user.onboarded_at is not None,
        budgets=[BudgetOut(name=b.name, period=b.period, limit_amount=b.limit_amount, currency=b.currency) for b in budgets],
        importance=importance,
        price_sensitivity=price_sens,
        avoid_materials=values("avoid.material."),
        like_merchants=values("like.merchant."),
        avoid_merchants=values("avoid.merchant."),
        likes=values("like.text."),
        dislikes=values("dislike.text."),
        lessons=[m.content for k, m in keyed.items() if k.startswith("lesson.")],
        recent_interest=recent_interest(session, user.id),
        spending=spending_summary(session, user.id, user.currency),
        scoring_weights=scoring_weights(importance),
        category_weights={
            c: scoring_weights(imp, frozenset(d for d in DIMENSIONS if imp[d] is not importance[d])) for c, imp in category_importance.items()
        },
        category_importance={c: {d: imp[d] for d in DIMENSIONS if imp[d] is not importance[d]} for c, imp in category_importance.items()},
        memory_count=len(memories),
    )
