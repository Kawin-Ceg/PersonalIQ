"""Currency conversion for display, budgets and cart planning.

The demo catalog is priced in USD. Each user has a home currency; every amount they see, and
every budget they set, is in that currency. Rates are FIXED demo rates (labelled in the UI),
not live market data. Decimal only.
"""

from decimal import ROUND_HALF_UP, Decimal

BASE = "USD"
RATES: dict[str, Decimal] = {  # units of currency per 1 USD
    "USD": Decimal("1"),
    "EUR": Decimal("0.93"),
    "GBP": Decimal("0.79"),
    "INR": Decimal("84.50"),
    "SEK": Decimal("10.70"),
}
SUPPORTED = tuple(RATES)
SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "SEK": "kr "}
CENT = Decimal("0.01")


def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return amount.quantize(CENT, ROUND_HALF_UP)
    return (amount / RATES[from_currency] * RATES[to_currency]).quantize(CENT, ROUND_HALF_UP)


def _indian_grouping(text: str) -> str:
    """'161815.82' -> '1,61,815.82' (last three digits, then pairs), matching the UI's en-IN format."""
    whole, _, frac = text.partition(".")
    head, tail = whole[:-3], whole[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join(([head] if head else []) + pairs + [tail])
    return f"{grouped}.{frac}" if frac else grouped


def fmt(amount: Decimal, currency: str) -> str:
    """Money for sentences the server writes, grouped the same way the UI shows it."""
    sign = "-" if amount < 0 else ""
    plain = f"{abs(amount):.2f}"
    number = _indian_grouping(plain) if currency == "INR" else f"{abs(amount):,.2f}"
    return f"{sign}{SYMBOL.get(currency, currency + ' ')}{number}"
