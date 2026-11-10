"""Learning loop: a poor aspect rating on a purchase changes future picks for that category only."""

from tests.test_payments import API, _approved, _checkout, paypal  # noqa: F401 (paypal is a fixture)


def test_poor_aspect_reweights_that_category_and_the_user_can_overrule_it(client, paypal):  # noqa: F811
    a = _approved(client)
    oid = a["order"]["id"]
    client.post(f"{API}/paypal/capture-order", json={"order_id": oid, "paypal_order_id": _checkout(client, paypal, oid)})
    item = next(i["product"] for i in a["items"] if i["product"]["category"] == "Furniture")
    need = item["attributes"]["need"]
    before = client.get("/api/v1/me/context").json()

    # 6/10 overall (no exclusion), but durability was poor.
    res = client.post("/api/v1/me/feedback", json={"order_id": oid, "product_id": item["id"], "rating": 6, "aspects": {"durability": 3}})
    assert res.status_code == 201, res.text
    learning = res.json()["learning"]
    dur = next(w for w in learning["weights"] if w["key"] == "durability")
    assert learning["changed"] and dur["after"] > dur["before"]
    memory = next(m for m in learning["memories"] if "Durability matters more for Furniture" in m["content"])
    assert memory["source"] == "feedback" and memory["confidence"] < 1  # learned, not confirmed

    ctx = client.get("/api/v1/me/context").json()
    assert ctx["category_weights"]["Furniture"]["durability"] > ctx["scoring_weights"]["durability"]
    assert ctx["scoring_weights"] == before["scoring_weights"] and "Kitchen" not in ctx["category_weights"]  # other kinds untouched

    ranked = client.get(f"/api/v1/products/ranked?need={need}").json()["ranked"]
    mine = next(r for r in ranked if r["product"]["id"] == item["id"])
    comp = next(c for c in mine["components"] if c["key"] == "durability")
    assert comp["value"] == 30 and comp["reason"].startswith("Your rating 3/10")  # your experience beats the catalog

    # The user can turn it down, or delete it, and the weights follow.
    client.patch(f"/api/v1/me/memories/{memory['memory_id']}", json={"level": "low"})
    assert client.get("/api/v1/me/context").json()["category_weights"]["Furniture"]["durability"] < ctx["scoring_weights"]["durability"]
    client.delete(f"/api/v1/me/memories/{memory['memory_id']}")
    assert "Furniture" not in client.get("/api/v1/me/context").json()["category_weights"]
