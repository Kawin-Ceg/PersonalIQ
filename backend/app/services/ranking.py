"""Deterministic product ranking.

Score(p) = wQ*Q + wV*V + wP*P + wR*R + wF*F, every component 0-100.
Weights come from the user's context (Personal Intelligence Engine) and sum to 1.

  Q  quality      curated quality score
  V  value        (quality + durability) per dollar, relative to the best value for the same need
  P  price        cheapest option for the need = 100, others scale by cheapest / price
  R  durability   curated durability score
  F  fit          preferences: liked store, a good past rating of this exact product, buyer rating

Hard constraints (avoided material, avoided store, a product you rated 5/10 or less, over a
price cap) exclude a product instead of lowering its score, and the reason is reported.

Learning from outcomes:
- If you rated an aspect of a category poorly, that category uses its own weights
  (e.g. durability weighs more for Furniture), from ctx.category_weights.
- If you rated an aspect of this exact product, your score (x10) replaces the catalog's
  quality or durability score for it.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Feedback, Product
from app.schemas.personal import UserContext
from app.services.fx import convert, fmt

COMPONENT_LABEL = {
    "quality": "Quality",
    "value": "Value for money",
    "price": "Price",
    "durability": "Durability",
    "fit": "Fits your preferences",
}


@dataclass
class Scored:
    product: Product
    score: float
    components: list[dict]
    rank: int = 0


@dataclass
class Ranking:
    ranked: list[Scored] = field(default_factory=list)  # ordered: by need, then score desc
    excluded: list[tuple[Product, list[str]]] = field(default_factory=list)

    def by_need(self) -> dict[str, list[Scored]]:
        groups: dict[str, list[Scored]] = defaultdict(list)
        for s in self.ranked:
            groups[need_of(s.product)].append(s)
        return groups


def need_of(p: Product) -> str:
    return (p.attributes or {}).get("need", "general")


def exclusion_reasons(p: Product, ctx: UserContext, max_price: Decimal | None, past: dict[uuid.UUID, int]) -> list[str]:
    reasons = []
    if p.id in past and past[p.id] <= 5:
        reasons.append(f"You rated this {past[p.id]}/10 before")
    materials = [m.lower() for m in (p.attributes or {}).get("materials", [])]
    for avoid in ctx.avoid_materials:
        hit = next((m for m in materials if avoid.lower() in m), None)
        if hit:
            reasons.append(f"Contains {hit}, which you avoid")
    if p.merchant.slug in ctx.avoid_merchants:
        reasons.append(f"Sold by {p.merchant.name}, which you avoid")
    if p.availability != "in_stock":
        reasons.append("Not in stock")
    # max_price is in the user's currency
    if max_price is not None and convert(p.price, p.currency, ctx.currency) > max_price:
        reasons.append(f"Over your limit of {fmt(max_price, ctx.currency)}")
    return reasons


def _past_ratings(session: Session, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = session.execute(select(Feedback.product_id, Feedback.rating).where(Feedback.user_id == user_id, Feedback.product_id.is_not(None)))
    return {pid: rating for pid, rating in rows}


def _past_aspects(session: Session, user_id: uuid.UUID) -> dict[uuid.UUID, dict[str, int]]:
    rows = session.execute(select(Feedback.product_id, Feedback.aspects).where(Feedback.user_id == user_id, Feedback.product_id.is_not(None)))
    return {pid: aspects for pid, aspects in rows if aspects}


def weights_for(ctx: UserContext, category: str) -> dict[str, float]:
    return ctx.category_weights.get(category, ctx.scoring_weights)


def _curated(p: Product, key: str, catalog: int, mine: dict[str, int]) -> tuple[int, str]:
    label = "Quality" if key == "quality" else "Durability"
    if key in mine:
        return mine[key] * 10, f"Your rating {mine[key]}/10 (catalog said {catalog}/100)"
    return catalog, f"{label} score {catalog}/100"


def _fit(p: Product, ctx: UserContext, past: dict[uuid.UUID, int]) -> tuple[int, str]:
    value, notes = 50, []
    if p.merchant.slug in ctx.like_merchants:
        value += 25
        notes.append(f"you like {p.merchant.name}")
    if past.get(p.id, 0) >= 8:  # ratings of 5 or less exclude the product instead
        value += 20
        notes.append(f"you rated this {past[p.id]}/10 before")
    if p.rating >= 4.6:
        value += 10
        notes.append(f"rated {p.rating:.1f} by {p.review_count:,} buyers")
    value = max(0, min(100, value))
    return value, ("Neutral: no preference signals" if not notes else "Because " + ", ".join(notes))


def rank_products(
    session: Session,
    products: list[Product],
    ctx: UserContext,
    max_price: Decimal | None = None,
) -> Ranking:
    past = _past_ratings(session, ctx.user_id)
    aspects = _past_aspects(session, ctx.user_id)
    out = Ranking()

    groups: dict[str, list[Product]] = defaultdict(list)
    for p in products:
        reasons = exclusion_reasons(p, ctx, max_price, past)
        if reasons:
            out.excluded.append((p, reasons))
        else:
            groups[need_of(p)].append(p)

    for need in sorted(groups):
        items = groups[need]
        cheapest = min(p.price for p in items)
        value_raw = {p.id: Decimal(p.quality_score + p.durability_score) / 2 / p.price for p in items}
        best_value = max(value_raw.values())

        scored = []
        for p in items:
            price_c = int(round(float(cheapest / p.price) * 100))
            value_c = int(round(float(value_raw[p.id] / best_value) * 100))
            fit_c, fit_reason = _fit(p, ctx, past)
            weights = weights_for(ctx, p.category)
            mine = aspects.get(p.id, {})
            quality_c, quality_why = _curated(p, "quality", p.quality_score, mine)
            durability_c, durability_why = _curated(p, "durability", p.durability_score, mine)
            parts = [
                ("quality", quality_c, quality_why),
                ("value", value_c, "Best value for this need" if value_c == 100 else f"{value_c}% of the best value for this need"),
                ("price", price_c, "Cheapest option" if price_c == 100 else f"{fmt(convert(p.price - cheapest, p.currency, ctx.currency), ctx.currency)} more than the cheapest"),
                ("durability", durability_c, durability_why),
                ("fit", fit_c, fit_reason),
            ]
            components = [
                {"key": k, "value": v, "weight": weights[k], "contribution": round(v * weights[k], 2), "reason": why}
                for k, v, why in parts
            ]
            score = round(sum(c["contribution"] for c in components), 1)
            scored.append(Scored(p, score, components))

        # Higher score first; ties go to the cheaper product.
        scored.sort(key=lambda s: (-s.score, s.product.price))
        for i, s in enumerate(scored, start=1):
            s.rank = i
        out.ranked.extend(scored)
    return out
