"""Financial intelligence: detection rules on fixed data, and budgets that count the right orders."""

from datetime import date, timedelta
from decimal import Decimal

from app.services.finance import Txn, _forecast, recurring, unusual
from tests.test_payments import API, _approved, _checkout, paypal  # noqa: F401 (paypal is a fixture)

TODAY = date(2026, 11, 10)


def _t(days_ago: int, merchant: str, category: str, amount: str, source: str = "uploaded") -> Txn:
    return Txn(TODAY - timedelta(days=days_ago), merchant, category, Decimal(amount), source)


def test_recurring_unusual_and_forecast_are_plain_arithmetic():
    txns = sorted([
        _t(75, "Streamly", "Subscriptions", "649"), _t(45, "Streamly", "Subscriptions", "649"), _t(15, "Streamly", "Subscriptions", "649"),
        _t(60, "FreshCart", "Groceries", "6000"), _t(41, "FreshCart", "Groceries", "7300"), _t(9, "FreshCart", "Groceries", "6600"),
        _t(50, "Shop", "Home", "3000"), _t(30, "Shop", "Home", "3400"), _t(5, "Big Store", "Home", "9000"),
        _t(3, "PayPal order", "Furniture", "150000", "paypal"),
    ], key=lambda t: t.on)

    rec = recurring(txns, TODAY)
    assert [r["merchant"] for r in rec] == ["Streamly"]  # steady monthly; groceries vary too much in timing
    assert rec[0]["next_expected"] == (TODAY + timedelta(days=15)).isoformat()

    odd = unusual(txns)
    assert [(u["merchant"], u["times_usual"]) for u in odd] == [("Big Store", "2.6")]  # 9000 vs median 3400

    fc = _forecast(txns, rec, TODAY, "INR")
    # So far this month: FreshCart 6600 (1 Nov) + Big Store 9000; the PayPal purchase is planned, not everyday.
    assert fc["so_far"] == "15600.00" and fc["recurring_still_due"] == "649.00"
    daily = Decimal(6000 + 7300 + 6600 + 3000 + 3400 + 9000) / 90
    assert fc["projected_total"] == f"{(Decimal(15600) + Decimal(649) + daily * 20).quantize(Decimal('0.01'))}"
    assert any("left out" in a for a in fc["assumptions"])


def test_budgets_count_only_their_own_orders(client, paypal):  # noqa: F811
    a = _approved(client)
    total = Decimal(a["order"]["total"])

    def budget(name):
        return next(b for b in client.get("/api/v1/finance/overview").json()["budgets"] if b["name"] == name)

    # Approved but unpaid money is committed ("in flight"), including mid-checkout.
    oid = a["order"]["id"]
    body = {"order_id": oid, "paypal_order_id": _checkout(client, paypal, oid)}
    assert Decimal(budget("Apartment move")["in_flight"]) == total
    client.post(f"{API}/paypal/capture-order", json=body)
    apt = budget("Apartment move")
    assert Decimal(apt["spent"]) == total and Decimal(apt["in_flight"]) == 0
    assert Decimal(budget("Monthly discretionary")["spent"]) == 0  # the apartment order isn't monthly spending

    over = client.post("/api/v1/finance/affordability", json={"amount": "50000", "budget_name": "Apartment move"}).json()
    assert over["verdict"] == "over" and Decimal(over["left_after"]) < 0
    assert client.post("/api/v1/finance/affordability", json={"amount": "10", "income": "1"}).status_code == 422


def test_written_summary_may_only_use_given_numbers():
    from app.services.finance import _complete_sentences, _numbers_match

    facts = "Spent so far this month: ₹14,479.00. Largest category: Groceries at 40%."
    assert _numbers_match("You've spent ₹14,479.00 so far; groceries are 40%.", facts)
    assert _numbers_match("About ₹14,479 so far.", facts)  # rounding a given number is fine
    assert not _numbers_match("You've spent ₹15,000.00 so far.", facts)  # an invented number falls back
    assert not _numbers_match("About ₹14,480 so far.", facts)
    assert _complete_sentences("One full sentence. And a cut-off") == "One full sentence."
