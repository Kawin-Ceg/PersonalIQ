from decimal import Decimal

from app.services.budget import evaluate

APARTMENT = ["mattress", "bed_frame", "sofa", "dining", "desk", "office_chair", "cookware", "microwave", "kettle", "tv", "vacuum", "sheets", "pillows", "towels"]
REQUIRED = {"mattress", "bed_frame", "sheets", "pillows"}


def test_ranking_is_personal_and_explained(client):
    body = client.get("/api/v1/products/ranked").json()  # Priya: avoids leather, rated the nonstick set 4/10
    excluded = {e["product"]["sku"]: e["reasons"] for e in body["excluded"]}
    assert any("leather" in r for r in excluded["FUR-009"])  # leather sofa
    assert any("leather" in r for r in excluded["FUR-015"])  # "bonded leather" chair
    assert excluded["KIT-002"] == ["You rated this 4/10 before"]

    for item in body["ranked"]:
        total = sum(c["contribution"] for c in item["components"])
        assert abs(total - item["score"]) < 0.11
        assert 0 <= item["score"] <= 100
    # Prices are shown in her currency, converted from the USD catalog price at the fixed demo rate.
    chair = next(i["product"] for i in body["ranked"] if i["product"]["sku"] == "FUR-014")
    assert (chair["currency"], chair["base_price"], chair["price"]) == ("INR", "149.99", "12674.16")

    chairs = [i for i in body["ranked"] if i["product"]["attributes"]["need"] == "office_chair"]
    assert chairs[0]["rank"] == 1 and chairs[0]["score"] == max(c["score"] for c in chairs)


def test_cart_fits_budget_with_shipping_and_keeps_required_items(client):
    needs = [{"need": n, "required": n in REQUIRED} for n in APARTMENT]
    # Priya's home currency is INR: the budget and every amount in the plan are in rupees.
    plan = client.post("/api/v1/cart/optimize", json={"budget": "169000", "needs": needs, "budget_name": "Apartment move"}).json()
    assert plan["feasible"] and plan["currency"] == "INR"
    total = Decimal(plan["total"])
    assert total <= Decimal("169000")
    assert total == Decimal(plan["subtotal"]) + Decimal(plan["shipping_total"])
    assert REQUIRED <= {l["need"] for l in plan["lines"]}
    assert "KIT-002" not in {l["product"]["sku"] for l in plan["lines"]}
    assert plan["budget_evaluation"]["within_budget"] is True

    # Too small for the required items: says so instead of returning a broken cart.
    tight = client.post("/api/v1/cart/optimize", json={"budget": "30000", "needs": needs}).json()
    assert tight["feasible"] is False and tight["lines"] == [] and "at least" in tight["message"]


def test_budget_math_is_exact():
    ok = evaluate("Monthly", Decimal("1000.00"), Decimal("600.00"), Decimal("300.00"))
    assert ok["remaining_after"] == Decimal("100.00") and ok["within_budget"] and ok["used_pct"] == 90
    over = evaluate("Monthly", Decimal("1000.00"), Decimal("600.00"), Decimal("450.10"))
    assert over["remaining_after"] == Decimal("-50.10") and not over["within_budget"]
    assert "$50.10 over" in over["explanation"]
