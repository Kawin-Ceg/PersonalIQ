"""What PayPal is asked to charge, derived only from the order in the database.

Orders are priced in the user's home currency. PayPal charges in PAYPAL_CURRENCY (USD by default),
so each line is converted at the fixed demo rate and the totals are rebuilt from the converted lines.
That keeps PayPal's own check (items x quantity = item_total, item_total + shipping + tax = total) exact.
The charge is part of the approval fingerprint, so the user approves both amounts.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.paypal.orders import ChargeLine, ChargeRequest
from app.models import Order, Product
from app.services.fx import RATES, convert

CENT = Decimal("0.01")
# Two-decimal currencies PayPal accepts (INR only for PayPal India accounts).
PAYPAL_CURRENCIES = {"AUD", "BRL", "CAD", "CZK", "DKK", "EUR", "HKD", "ILS", "MXN", "NZD", "NOK", "PHP", "PLN", "GBP", "SGD", "SEK", "CHF", "THB", "USD", "INR"}


class SettlementError(Exception):
    pass


@dataclass(frozen=True)
class Charge:
    currency: str
    item_total: Decimal
    shipping: Decimal
    tax: Decimal
    total: Decimal
    rate_note: str  # e.g. "1 USD = 84.50 INR (fixed demo rate)"

    def as_dict(self) -> dict:
        return {
            "currency": self.currency, "item_total": f"{self.item_total:.2f}", "shipping": f"{self.shipping:.2f}",
            "tax": f"{self.tax:.2f}", "total": f"{self.total:.2f}", "rate_note": self.rate_note,
        }


def charge_currency() -> str:
    cur = get_settings().paypal_currency.upper()
    if cur not in PAYPAL_CURRENCIES or cur not in RATES:
        raise SettlementError(f"PAYPAL_CURRENCY {cur} isn't supported.")
    return cur


def _unit(order: Order, unit_price: Decimal, cur: str) -> Decimal:
    return convert(unit_price, order.currency, cur)


def charge_for(order: Order) -> Charge:
    cur = charge_currency()
    if order.currency not in RATES:
        raise SettlementError(f"Order currency {order.currency} isn't supported.")
    item_total = sum((_unit(order, i.unit_price, cur) * i.quantity for i in order.items), Decimal("0")).quantize(CENT)
    shipping = convert(order.shipping, order.currency, cur)
    tax = convert(order.tax, order.currency, cur)
    note = "" if cur == order.currency else f"1 {cur} = {RATES[order.currency] / RATES[cur]:.2f} {order.currency} (fixed demo rate)"
    return Charge(cur, item_total, shipping, tax, (item_total + shipping + tax).quantize(CENT), note)


def charge_request(session: Session, order: Order, description: str) -> ChargeRequest:
    cur = charge_currency()
    c = charge_for(order)
    lines = []
    for i in order.items:
        p = session.get(Product, i.product_id)
        lines.append(ChargeLine(name=p.name, sku=p.sku, quantity=i.quantity, unit_amount=_unit(order, i.unit_price, cur)))
    return ChargeRequest(
        reference_id=str(order.id), description=description, currency=c.currency,
        item_total=c.item_total, shipping=c.shipping, tax=c.tax, total=c.total, lines=tuple(lines),
    )


def arithmetic_problems(order: Order) -> list[str]:
    """Re-add the order from its lines. Any mismatch means the stored order can't be trusted."""
    problems = []
    for i in order.items:
        if i.quantity < 1:
            problems.append("an item has a quantity below 1")
        if (i.unit_price * i.quantity).quantize(CENT) != i.line_total:
            problems.append("an item's line total doesn't match price x quantity")
    if sum((i.line_total for i in order.items), Decimal("0")).quantize(CENT) != order.subtotal:
        problems.append("the subtotal doesn't match the items")
    if (order.subtotal + order.shipping + order.tax).quantize(CENT) != order.total:
        problems.append("the total doesn't match subtotal + shipping + tax")
    if order.total <= 0:
        problems.append("the total isn't positive")
    return problems
