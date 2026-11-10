"""Risk policy: decides how much of the user's attention each item in a proposed order needs.

Deterministic and explainable: every factor adds or removes points with a plain reason.
  score >= 40  needs_decision   the user must keep, swap or remove it before approving
  score >= 20  review           shown first, no action required
  otherwise    auto             PersonalIQ is confident

This never removes the final approval: paying always needs the user's explicit yes on the exact
order. It decides where the user should look before saying yes.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.services.fx import fmt

NEEDS_DECISION = 40
REVIEW = 20


@dataclass
class ItemFacts:
    item_id: str
    name: str
    need: str
    category: str
    merchant_slug: str
    merchant_name: str
    line_total: Decimal
    required: bool
    rank: int  # 1 = the Buyer agent's top match for this need
    score: float
    runner_up_name: str | None = None
    runner_up_score: float | None = None
    top_name: str | None = None
    top_score: float | None = None
    return_days: int = 30
    duplicate: bool = False


@dataclass
class UserFacts:
    currency: str
    budget_limit: Decimal | None
    monthly_average: Decimal | None  # from uploaded spending
    category_ratings: dict[str, float] = field(default_factory=dict)  # category -> average past rating /10
    category_counts: dict[str, int] = field(default_factory=dict)
    liked_merchants: set[str] = field(default_factory=set)  # slugs
    known_merchants: set[str] = field(default_factory=set)  # names seen in spending history


def assess_item(item: ItemFacts, user: UserFacts) -> dict:
    factors: list[dict] = []

    def add(points: int, factor: str, reason: str) -> None:
        factors.append({"factor": factor, "points": points, "reason": reason})

    cur = user.currency
    if user.budget_limit and user.budget_limit > 0:
        share = item.line_total / user.budget_limit
        if share >= Decimal("0.30"):
            add(30, "amount", f"Takes {share:.0%} of the {fmt(user.budget_limit, cur)} budget.")
        elif share >= Decimal("0.15"):
            add(15, "amount", f"Takes {share:.0%} of the budget.")
        if not item.required and share >= Decimal("0.10"):
            add(10, "nice_to_have", f"A nice-to-have costing {fmt(item.line_total, cur)}.")
    if user.monthly_average and item.line_total > user.monthly_average / 2:
        add(15, "vs_usual_spend", f"More than half your usual monthly spending ({fmt(user.monthly_average, cur)}).")

    avg = user.category_ratings.get(item.category)
    if avg is not None:
        n = user.category_counts.get(item.category, 1)
        if avg < 6:
            add(20, "past_outcomes", f"Your past {item.category.lower()} purchases averaged {avg:.0f}/10 ({n} rated).")
        elif avg >= 8:
            add(-10, "past_outcomes", f"Your past {item.category.lower()} purchases went well ({avg:.0f}/10).")

    if item.rank > 1 and item.top_name:
        add(20, "budget_swap", f"Not your top match: {item.top_name} scored {item.top_score:.1f}, this was picked to stay within budget.")
    elif item.runner_up_score is not None and item.score - item.runner_up_score < 2:
        add(15, "close_call", f"Close call: {item.runner_up_name} scored {item.runner_up_score:.1f} vs {item.score:.1f}.")

    if item.return_days < 30:
        add(10, "returns", f"Only {item.return_days}-day returns at {item.merchant_name}.")
    if item.merchant_slug in user.liked_merchants:
        add(-5, "liked_store", f"You like shopping at {item.merchant_name}.")
    elif item.merchant_name not in user.known_merchants:
        add(5, "new_store", f"First purchase from {item.merchant_name}.")
    if item.duplicate:
        add(30, "duplicate", f"You bought a {item.need.replace('_', ' ')} recently.")

    score = max(0, min(100, sum(f["points"] for f in factors)))
    level = "needs_decision" if score >= NEEDS_DECISION else "review" if score >= REVIEW else "auto"
    return {"score": score, "level": level, "factors": factors}


def assess_order(total: Decimal, user: UserFacts, items: dict[str, dict]) -> dict:
    factors = []
    if user.budget_limit and user.budget_limit > 0:
        used = total / user.budget_limit
        if used > 1:
            factors.append({"factor": "over_budget", "points": 100, "reason": f"{fmt(total - user.budget_limit, user.currency)} over the budget."})
        elif used >= Decimal("0.9"):
            factors.append({"factor": "budget_used", "points": 15, "reason": f"Uses {used:.0%} of the budget."})
    counts = {lvl: sum(1 for r in items.values() if r["level"] == lvl) for lvl in ("needs_decision", "review", "auto")}
    return {"factors": factors, "counts": counts, "over_budget": any(f["factor"] == "over_budget" for f in factors)}
