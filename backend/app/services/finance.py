"""Financial intelligence. Every number here is computed in Python with Decimal from stored data:
uploaded transactions, PayPal-verified purchases and saved budgets. The LLM may only rephrase
the finished facts (see `explain`), never produce a number.

All amounts are in the user's home currency. Transactions in other currencies are skipped.
"""

import calendar
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, Transaction, User
from app.services.budget import budget_usage, evaluate
from app.services.fx import fmt

CENT = Decimal("0.01")
WINDOW = 90  # days of history for averages and categories
RECURRING_LOOKBACK = 180
UNUSUAL_FACTOR = Decimal("2")  # more than 2x the category's median
CADENCES = {"weekly": (7, 2), "monthly": (30, 5)}  # (typical gap in days, allowed drift)


@dataclass
class Txn:
    on: date
    merchant: str
    category: str
    amount: Decimal
    source: str


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, ROUND_HALF_UP)


def _s(x: Decimal | None) -> str | None:
    return None if x is None else f"{_q(x):.2f}"


def _pct(part: Decimal, whole: Decimal) -> int:
    return int((part / whole * 100).quantize(Decimal(1), ROUND_HALF_UP)) if whole > 0 else 0


def _txns(session: Session, user: User, since: date) -> list[Txn]:
    rows = session.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.occurred_on >= since, Transaction.currency == user.currency)
    )
    return sorted((Txn(r.occurred_on, r.merchant, r.category, r.amount, r.source) for r in rows), key=lambda t: t.on)


def _month_start(d: date, back: int = 0) -> date:
    y, m = d.year, d.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


# ---------- recurring ----------


def recurring(txns: list[Txn], today: date) -> list[dict]:
    """Same merchant, at least 3 payments, at a steady weekly or monthly gap, for nearly the same amount."""
    by_merchant: dict[str, list[Txn]] = defaultdict(list)
    for t in txns:
        if t.source != "paypal":  # one-off planned purchases aren't subscriptions
            by_merchant[t.merchant.strip().lower()].append(t)
    out = []
    for items in by_merchant.values():
        if len(items) < 3:
            continue
        gaps = [(b.on - a.on).days for a, b in zip(items, items[1:])]
        amounts = [t.amount for t in items]
        if min(amounts) <= 0 or max(amounts) / min(amounts) > Decimal("1.15"):
            continue
        typical_gap = statistics.median(gaps)
        cadence = next((name for name, (gap, drift) in CADENCES.items() if all(abs(g - gap) <= drift for g in gaps) and abs(typical_gap - gap) <= drift), None)
        if cadence is None:
            continue
        amount = _q(Decimal(str(statistics.median(amounts))))
        days = CADENCES[cadence][0]
        nxt = items[-1].on + timedelta(days=round(typical_gap))
        while nxt < today:  # missed or not uploaded yet: roll forward, don't pretend it happened
            nxt += timedelta(days=round(typical_gap))
        out.append({
            "merchant": items[-1].merchant, "category": items[-1].category, "cadence": cadence, "amount": _s(amount),
            "monthly_cost": _s(amount * Decimal(30) / Decimal(days)), "times_seen": len(items),
            "last_paid": items[-1].on.isoformat(), "next_expected": nxt.isoformat(),
        })
    return sorted(out, key=lambda r: Decimal(r["monthly_cost"]), reverse=True)


# ---------- unusual ----------


def unusual(txns: list[Txn]) -> list[dict]:
    """A payment over twice the median for its category (categories with at least 3 payments)."""
    by_cat: dict[str, list[Txn]] = defaultdict(list)
    for t in txns:
        by_cat[t.category].append(t)
    out = []
    for cat, items in by_cat.items():
        if len(items) < 3:
            continue
        median = Decimal(str(statistics.median([t.amount for t in items])))
        for t in items:
            if t.amount > median * UNUSUAL_FACTOR:
                times = (t.amount / median).quantize(Decimal("0.1"), ROUND_HALF_UP)
                out.append({
                    "on": t.on.isoformat(), "merchant": t.merchant, "category": cat, "amount": _s(t.amount),
                    "usual": _s(median), "times_usual": f"{times}",
                })
    return sorted(out, key=lambda u: u["on"], reverse=True)


# ---------- the overview ----------


def overview(session: Session, user: User, today: date | None = None) -> dict:
    today = today or date.today()
    cur = user.currency
    txns = _txns(session, user, today - timedelta(days=RECURRING_LOOKBACK))
    window = [t for t in txns if t.on > today - timedelta(days=WINDOW)]

    # Months: this one so far and the three before it.
    months = []
    for back in range(3, -1, -1):
        start = _month_start(today, back)
        end = _month_start(today, back - 1) if back else today + timedelta(days=1)
        items = [t for t in txns if start <= t.on < end]
        months.append({
            "month": start.strftime("%Y-%m"), "label": start.strftime("%b %Y"), "partial": back == 0,
            "total": _s(sum((t.amount for t in items), Decimal(0))),
            "everyday": _s(sum((t.amount for t in items if t.source != "paypal"), Decimal(0))),
            "planned": _s(sum((t.amount for t in items if t.source == "paypal"), Decimal(0))),
        })

    # Everyday categories over the window (planned purchases would swamp them), and how the last
    # 30 days compare with the 30 before.
    everyday = [t for t in window if t.source != "paypal"]
    total = sum((t.amount for t in everyday), Decimal(0))
    cats: dict[str, dict] = defaultdict(lambda: {"total": Decimal(0), "recent": Decimal(0), "prior": Decimal(0), "count": 0})
    for t in everyday:
        c = cats[t.category]
        c["total"] += t.amount
        c["count"] += 1
        age = (today - t.on).days
        if age < 30:
            c["recent"] += t.amount
        elif age < 60:
            c["prior"] += t.amount
    categories = [
        {"category": k, "total": _s(v["total"]), "share_pct": _pct(v["total"], total), "count": v["count"],
         "last_30": _s(v["recent"]), "prior_30": _s(v["prior"]),
         "change_pct": _pct(v["recent"] - v["prior"], v["prior"]) if v["prior"] > 0 else None}
        for k, v in sorted(cats.items(), key=lambda kv: kv[1]["total"], reverse=True)
    ]

    rec = recurring(txns, today)
    forecast = _forecast(window, rec, today, cur)

    monthly_avg = _q(sum((t.amount for t in everyday), Decimal(0)) / Decimal(WINDOW) * Decimal(30)) if everyday else None

    return {
        "currency": cur, "as_of": today.isoformat(), "window_days": WINDOW,
        "has_data": bool(txns),
        "transaction_count": len(window),
        "sources": {"uploaded": sum(1 for t in window if t.source == "uploaded"), "paypal": sum(1 for t in window if t.source == "paypal")},
        "months": months,
        "everyday_monthly_average": _s(monthly_avg),
        "planned_total": _s(sum((t.amount for t in window if t.source == "paypal"), Decimal(0))),
        "categories": categories,
        "recurring": rec,
        "recurring_monthly_total": _s(sum((Decimal(r["monthly_cost"]) for r in rec), Decimal(0))),
        "unusual": unusual(everyday),
        "forecast": forecast,
        "budgets": budgets(session, user, today),
    }


def _forecast(window: list[Txn], rec: list[dict], today: date, cur: str) -> dict:
    """Everyday spending projected to the end of this month. Planned PayPal purchases are left out:
    they're tracked by their budgets, not guessed."""
    month_start = _month_start(today)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = days_in_month - today.day
    so_far = sum((t.amount for t in window if t.on >= month_start and t.source != "paypal"), Decimal(0))

    rec_merchants = {r["merchant"].strip().lower() for r in rec}
    variable = [t for t in window if t.source != "paypal" and t.merchant.strip().lower() not in rec_merchants]
    daily = sum((t.amount for t in variable), Decimal(0)) / Decimal(WINDOW)
    month_end = date(today.year, today.month, days_in_month)
    due = [r for r in rec if today < date.fromisoformat(r["next_expected"]) <= month_end]
    recurring_left = sum((Decimal(r["amount"]) for r in due), Decimal(0))
    projected = _q(so_far + recurring_left + daily * days_left)
    return {
        "month": today.strftime("%B %Y"), "so_far": _s(so_far), "days_left": days_left,
        "recurring_still_due": _s(recurring_left), "recurring_due": [r["merchant"] for r in due],
        "daily_variable_rate": _s(daily), "projected_total": _s(projected),
        "assumptions": [
            f"Everyday spending (not counting recurring payments) continues at the last {WINDOW} days' average of {fmt(_q(daily), cur)} a day.",
            "Recurring payments land on their usual dates." if due else "No recurring payment is due before the month ends.",
            "Planned purchases paid through PersonalIQ are left out; they're tracked against their budgets.",
            "Only uploaded and PayPal-verified transactions are known. Anything else is missing.",
        ],
    }


# ---------- budgets and affordability ----------


def budgets(session: Session, user: User, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out = []
    for b in session.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.name)):
        u = budget_usage(session, user.id, b, today)
        used = u["spent"] + u["in_flight"]
        left = b.limit_amount - used
        out.append({
            "name": b.name, "period": b.period, "currency": b.currency,
            "period_label": today.strftime("%B %Y") if b.period == "monthly" else "One-off",
            "limit": _s(b.limit_amount), "spent": _s(u["spent"]), "in_flight": _s(u["in_flight"]), "left": _s(left),
            "used_pct": _pct(used, b.limit_amount), "over": left < 0,
        })
    return out


class AffordabilityError(Exception):
    pass


def affordability(session: Session, user: User, amount: Decimal, budget_name: str | None, today: date | None = None) -> dict:
    """Can this amount be spent? Checks the chosen budget (default: the monthly one) and puts it next
    to this month's projected everyday spending. We don't know income, so we don't claim savings."""
    today = today or date.today()
    cur = user.currency
    all_budgets = {b.name: b for b in session.scalars(select(Budget).where(Budget.user_id == user.id))}
    budget = all_budgets.get(budget_name) if budget_name else next((b for b in all_budgets.values() if b.period == "monthly"), None)
    if budget_name and budget is None:
        raise AffordabilityError("No budget with that name.")
    amount = _q(amount)
    lines, verdict, ev = [], "unknown", None

    if budget is not None:
        u = budget_usage(session, user.id, budget, today)
        ev = evaluate(budget.name, budget.limit_amount, u["spent"] + u["in_flight"], amount, cur)
        verdict = "over" if not ev["within_budget"] else "tight" if ev["used_pct"] >= 90 else "fits"
        lines.append(ev["explanation"])
        if u["in_flight"] > 0:
            lines.append(f"{fmt(u['in_flight'], cur)} of it is already approved for orders that aren't paid yet.")
    else:
        lines.append("You have no saved budget to check this against.")

    txns = _txns(session, user, today - timedelta(days=RECURRING_LOOKBACK))
    window = [t for t in txns if t.on > today - timedelta(days=WINDOW)]
    fc = _forecast(window, recurring(txns, today), today, cur)
    everyday = [t for t in window if t.source != "paypal"]
    if everyday:
        avg = _q(sum((t.amount for t in everyday), Decimal(0)) / Decimal(WINDOW) * Decimal(30))
        share = _pct(amount, avg) if avg > 0 else None
        lines.append(f"Everyday spending this month is heading for about {fmt(Decimal(fc['projected_total']), cur)} (usual month: {fmt(avg, cur)}).")
        if share is not None:
            lines.append(f"This purchase is {share}% of a usual month's everyday spending.")
    lines.append("Your income isn't known, so this checks budgets and habits, not savings.")

    return {
        "amount": _s(amount), "currency": cur, "verdict": verdict, "budget": budget.name if budget else None,
        "left_after": _s(ev["remaining_after"]) if ev else None, "used_pct_after": ev["used_pct"] if ev else None,
        "lines": lines,
    }


# ---------- words (optional LLM) ----------


def explain(data: dict) -> tuple[str, bool]:
    """Two or three plain sentences from finished numbers. Falls back to a fixed summary."""
    from app.agents.llm import get_llm

    cur = data["currency"]
    m = data["months"]
    fc = data["forecast"]
    top = data["categories"][0] if data["categories"] else None
    facts = [
        f"Spent so far this month (everyday): {fmt(Decimal(fc['so_far']), cur)}; projected month end {fmt(Decimal(fc['projected_total']), cur)}.",
        f"Last full month everyday: {fmt(Decimal(m[-2]['everyday']), cur)}." if len(m) > 1 else "",
        f"Usual month everyday: {fmt(Decimal(data['everyday_monthly_average']), cur)}." if data["everyday_monthly_average"] else "",
        f"Largest category over {data['window_days']} days: {top['category']} at {top['share_pct']}%." if top else "",
        f"Recurring payments: {len(data['recurring'])}, about {fmt(Decimal(data['recurring_monthly_total']), cur)} a month." if data["recurring"] else "",
        f"Unusual payments: {len(data['unusual'])}." if data["unusual"] else "No unusual payments.",
        *[f"Budget {b['name']}: {b['used_pct']}% used, {fmt(Decimal(b['left']), cur)} left." for b in data["budgets"]],
    ]
    facts_text = "\n".join(f for f in facts if f)
    fallback = " ".join(f for f in facts[:2] if f)
    text, by_llm = get_llm().write(
        "In at most three short, plain sentences (under 60 words), tell this person the most useful things about their spending. "
        "Pick what matters; don't list everything. Use only numbers given below, copied exactly. No advice about investments.",
        facts_text, fallback, max_tokens=300,
    )
    if not by_llm:
        return text, False
    text = _complete_sentences(text)
    if not text or not _numbers_match(text, facts_text):
        return fallback, False  # the model cut off, or used a number we didn't give it
    return text, True


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_match(text: str, facts: str) -> bool:
    """Every number in the written text must be one of the facts' numbers, exactly or rounded to a
    whole unit (₹35,768.89 may be written ₹35,769). Anything else means the model made it up."""
    known: set[str] = set()
    for x in _NUMBER.findall(facts):
        plain = x.replace(",", "")
        known.add(plain)
        if "." in plain:
            known.add(str(Decimal(plain).quantize(Decimal(1), ROUND_HALF_UP)))
    return all(x.replace(",", "") in known for x in _NUMBER.findall(text))


def _complete_sentences(text: str) -> str:
    text = text.strip()
    if text.endswith((".", "!", "?")):
        return text
    cut = max(text.rfind(". "), text.rfind("! "), text.rfind("? "))
    return text[: cut + 1].strip() if cut > 0 else ""
