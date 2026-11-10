import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Approval, Order
from app.services.risk import ItemFacts, UserFacts, assess_item


def _ready_approval(client) -> dict:
    wf = client.post("/api/v1/workflows", json={"message": "Set up my new apartment with the essentials"}).json()
    wf = client.get(f"/api/v1/workflows/{wf['id']}").json()
    assert wf["status"] == "awaiting_approval"
    return client.get(f"/api/v1/approvals/{wf['result']['approval_id']}").json()


def test_approval_needs_decisions_then_the_exact_order(client, session):
    a = _ready_approval(client)
    must = [i for i in a["items"] if i["risk"]["level"] == "needs_decision"]
    assert must, "an apartment cart should have at least one big-ticket item to decide on"
    assert all(i["trail"][0]["step"] == "Ranked" and i["risk"]["factors"] for i in must)  # explained, not magic

    blocked = client.post(f"/api/v1/approvals/{a['id']}/approve", json={"order_hash": a["order_hash"]})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "decisions_needed"

    for item in must:
        client.post(f"/api/v1/approvals/{a['id']}/items/{item['id']}", json={"action": "keep"})
    done = client.post(f"/api/v1/approvals/{a['id']}/approve", json={"order_hash": a["order_hash"]}).json()
    assert done["status"] == "approved" and done["order"]["status"] == "approved"


def test_changing_the_order_replaces_the_approval(client, session):
    a = _ready_approval(client)
    cheapest = min(a["items"], key=lambda i: Decimal(i["line_total"]))
    b = client.post(f"/api/v1/approvals/{a['id']}/items/{cheapest['id']}", json={"action": "remove"}).json()

    assert b["id"] != a["id"] and b["order_version"] == a["order_version"] + 1
    assert Decimal(b["order"]["total"]) < Decimal(a["order"]["total"])
    assert session.get(Approval, uuid.UUID(a["id"])).status == "superseded"

    old = client.post(f"/api/v1/approvals/{a['id']}/approve", json={"order_hash": a["order_hash"]})
    assert old.status_code == 409  # the old "yes" can't pay for the new order
    stale = client.post(f"/api/v1/approvals/{b['id']}/approve", json={"order_hash": a["order_hash"]})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale"
    assert any(e["title"].startswith("You removed") for e in b["timeline"])


def test_expired_approval_cannot_be_used(client, session):
    a = _ready_approval(client)
    row = session.get(Approval, uuid.UUID(a["id"]))
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()
    res = client.post(f"/api/v1/approvals/{a['id']}/approve", json={"order_hash": a["order_hash"]})
    assert res.status_code == 410
    assert session.get(Order, uuid.UUID(a["order"]["id"])).status == "expired"


def test_risk_policy_weighs_amount_history_and_alternatives():
    user = UserFacts(
        currency="INR", budget_limit=Decimal("100000"), monthly_average=Decimal("30000"),
        category_ratings={"Furniture": 4.0, "Kitchen": 9.0}, category_counts={"Furniture": 2, "Kitchen": 1},
        liked_merchants={"kettlewell"}, known_merchants=set(),
    )
    risky = ItemFacts(
        item_id="a", name="Sofa", need="sofa", category="Furniture", merchant_slug="harbor-pine", merchant_name="Harbor & Pine Home",
        line_total=Decimal("35000"), required=False, rank=2, score=80, top_name="Leather-free Sofa", top_score=84,
    )
    calm = ItemFacts(
        item_id="b", name="Kettle", need="kettle", category="Kitchen", merchant_slug="kettlewell", merchant_name="Kettlewell Kitchen",
        line_total=Decimal("3400"), required=True, rank=1, score=88, runner_up_name="Other kettle", runner_up_score=70,
    )
    r, c = assess_item(risky, user), assess_item(calm, user)
    assert r["level"] == "needs_decision"
    assert {f["factor"] for f in r["factors"]} >= {"amount", "nice_to_have", "vs_usual_spend", "past_outcomes", "budget_swap"}
    assert c["level"] == "auto"  # cheap, top match, a store and category that went well before
