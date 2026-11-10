"""Cart optimizer (used by the Procurement agent). Deterministic.

Multiple-choice knapsack: for every requested need pick at most one product (exactly one if the
need is required), maximising the total ranking score, subject to

    sum(price * quantity) + shipping <= budget

Everything runs in the user's home currency (prices and shipping rules are converted first).

Solved with dynamic programming over budget "steps". A step is a whole currency unit, or larger
for big budgets (a 169,000 rupee budget would otherwise mean 169,000 cells), so the table never
exceeds about MAX_STEPS cells. Costs are rounded UP to a step, so any plan the DP accepts fits the
real budget. Shipping depends on which merchants end up in the cart (flat fee, free over a
threshold): we solve, price the cart exactly, and if shipping pushes it over, shrink the item
budget by the overage and solve again.
"""

import math
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models import Merchant, Product
from app.schemas.catalog import product_out
from app.schemas.commerce import BudgetEvaluation, CartLine, CartPlan, CartRequest, MerchantShipping, SkippedNeed
from app.schemas.personal import UserContext
from app.services.budget import evaluate_saved_budget
from app.services.fx import convert, fmt
from app.services.ranking import Scored, rank_products

CENT = Decimal("0.01")
OPTIONS_PER_NEED = 4
OPTIONAL_WEIGHT = 0.8  # an optional need adds a little less value than a required one
MAX_SHIPPING_ROUNDS = 12
MAX_STEPS = 4000


def _solve(groups, prices: dict, step: Decimal, budget_steps: int):
    """Picks (one Scored or None per group) maximising utility, or None if required needs can't fit."""
    dp: list = [None] * (budget_steps + 1)
    dp[0] = (0.0, Decimal("0"), ())  # (utility, exact cost for tie-break, picks)
    for _need, required, qty, options in groups:
        new: list = [None] * (budget_steps + 1)
        if not required:
            new = [None if s is None else (s[0], s[1], s[2] + (None,)) for s in dp]
        for c, state in enumerate(dp):
            if state is None:
                continue
            for opt in options:
                exact = prices[opt.product.id] * qty
                cc = c + math.ceil(exact / step)
                if cc > budget_steps:
                    continue
                util = state[0] + opt.score * (1.0 if required else OPTIONAL_WEIGHT)
                cost = state[1] + exact
                cur = new[cc]
                # Prefer more utility; on a tie, the cheaper cart.
                if cur is None or util > cur[0] + 1e-9 or (abs(util - cur[0]) <= 1e-9 and cost < cur[1]):
                    new[cc] = (util, cost, state[2] + (opt,))
        dp = new
    best = None
    for s in dp:
        if s is not None and (best is None or s[0] > best[0] + 1e-9 or (abs(s[0] - best[0]) <= 1e-9 and s[1] < best[1])):
            best = s
    return None if best is None else list(best[2])


def _shipping(lines: list[CartLine], merchants: dict[str, Merchant], currency: str) -> list[MerchantShipping]:
    by_merchant: dict[str, list[CartLine]] = defaultdict(list)
    for line in lines:
        by_merchant[line.product.merchant.slug].append(line)
    out = []
    for slug, ls in by_merchant.items():
        m = merchants[slug]
        subtotal = sum((l.line_total for l in ls), Decimal("0"))
        flat = convert(m.shipping_flat, m.currency, currency)
        free_over = convert(m.free_shipping_over, m.currency, currency) if m.free_shipping_over is not None else None
        if free_over is not None and subtotal >= free_over:
            out.append(MerchantShipping(merchant=m.name, subtotal=subtotal, shipping=Decimal("0.00"), note=f"Free over {fmt(free_over, currency)}"))
        else:
            note = "Flat rate" if free_over is None else f"Flat rate, free over {fmt(free_over, currency)}"
            out.append(MerchantShipping(merchant=m.name, subtotal=subtotal, shipping=flat, note=note))
    return out


def _line(need: str, qty: int, chosen: Scored, options: list[Scored], prices: dict, currency: str) -> CartLine:
    p = chosen.product
    top = options[0]
    if chosen is top:
        reason = f"Top-ranked {need.replace('_', ' ')} for you (score {chosen.score:.1f})."
    else:
        saved = (prices[top.product.id] - prices[p.id]) * qty
        reason = f"Chosen over {top.product.name} (score {top.score:.1f}) to stay within budget. Saves {fmt(saved, currency)}."
    unit = prices[p.id]
    return CartLine(
        need=need, product=product_out(p, currency), quantity=qty, unit_price=unit,
        line_total=(unit * qty).quantize(CENT), score=chosen.score, reason=reason,
    )


def optimize_cart(
    session: Session,
    products: list[Product],
    ctx: UserContext,
    req: CartRequest,
    by_need: dict[str, list[Scored]] | None = None,
) -> CartPlan:
    """`by_need` lets the Procurement agent reuse the Buyer agent's ranking instead of ranking again."""
    cur = ctx.currency
    budget = req.budget.quantize(CENT)  # in the user's currency
    merchants = {p.merchant.slug: p.merchant for p in products}
    prices = {p.id: convert(p.price, p.currency, cur) for p in products}
    if by_need is None:
        by_need = rank_products(session, products, ctx).by_need()

    groups: list[tuple[str, bool, int, list[Scored]]] = []
    skipped: list[SkippedNeed] = []
    missing_required: list[str] = []
    seen = set()
    for n in req.needs:
        if n.need in seen:
            continue
        seen.add(n.need)
        options = by_need.get(n.need, [])[:OPTIONS_PER_NEED]
        if not options:
            skipped.append(SkippedNeed(need=n.need, reason="No product in the catalog that fits your preferences."))
            if n.required:
                missing_required.append(n.need)
            continue
        groups.append((n.need, n.required, n.quantity, options))

    def plan(feasible: bool, message: str, lines: list[CartLine], ship: list[MerchantShipping]) -> CartPlan:
        subtotal = sum((l.line_total for l in lines), Decimal("0")).quantize(CENT)
        ship_total = sum((s.shipping for s in ship), Decimal("0")).quantize(CENT)
        total = (subtotal + ship_total).quantize(CENT, ROUND_HALF_UP)
        evaluation = None
        if req.budget_name and lines:
            raw = evaluate_saved_budget(session, ctx.user_id, req.budget_name, total)
            evaluation = BudgetEvaluation(**raw) if raw else None
        return CartPlan(
            feasible=feasible, message=message, lines=lines, skipped=skipped, shipping=ship,
            subtotal=subtotal, shipping_total=ship_total, tax=Decimal("0.00"), total=total,
            budget=budget, remaining=(budget - total).quantize(CENT), currency=cur, budget_evaluation=evaluation,
        )

    if missing_required:
        names = ", ".join(n.replace("_", " ") for n in missing_required)
        return plan(False, f"Can't build this cart: nothing acceptable for {names}.", [], [])

    step = max(Decimal(1), Decimal(math.ceil(budget / MAX_STEPS)))

    def attempt(gs):
        """Solve, price exactly, and shrink the item budget by any shipping overage until it fits.
        Returns (picks, lines, shipping) or None."""
        reserve = Decimal("0")
        for _ in range(MAX_SHIPPING_ROUNDS):
            budget_steps = math.floor((budget - reserve) / step)
            picks = _solve(gs, prices, step, budget_steps) if budget_steps >= 0 else None
            if picks is None:
                return None
            lines = [_line(need, qty, pick, opts, prices, cur) for (need, _r, qty, opts), pick in zip(gs, picks) if pick is not None]
            ship = _shipping(lines, merchants, cur)
            total = sum((l.line_total for l in lines), Decimal("0")) + sum((s.shipping for s in ship), Decimal("0"))
            if total <= budget:
                return picks, lines, ship
            reserve += total - budget
        return None

    # Nice-to-haves from extra stores add their own shipping and can keep tipping the cart over.
    # If the full search can't settle, fall back to must-haves only before giving up.
    required_only = [g for g in groups if g[1]]
    for gs in (groups, required_only):
        if not gs:
            continue
        found = attempt(gs)
        if found:
            picks, lines, ship = found
            chosen = {need for (need, *_), pick in zip(gs, picks) if pick is not None}
            for need, required, _q, _o in groups:
                if not required and need not in chosen:
                    skipped.append(SkippedNeed(need=need, reason="Left out to stay within budget."))
            total = sum((l.line_total for l in lines), Decimal("0")) + sum((s.shipping for s in ship), Decimal("0"))
            return plan(True, f"{len(lines)} items for {fmt(total, cur)}, within your {fmt(budget, cur)} budget.", lines, ship)

    minimum = sum((min(prices[o.product.id] for o in opts) * qty for _n, required, qty, opts in groups if required), Decimal("0"))
    if minimum > budget:
        return plan(False, f"The required items cost at least {fmt(minimum, cur)} before shipping, more than the {fmt(budget, cur)} budget.", [], [])
    return plan(False, f"The required items fit the {fmt(budget, cur)} budget, but not once shipping is added.", [], [])
