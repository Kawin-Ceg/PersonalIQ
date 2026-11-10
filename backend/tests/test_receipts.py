"""Decision Receipt + Post-Purchase agent, using the fake PayPal from test_payments."""

import uuid

from sqlalchemy import func, select

from app.models import AgentRun, Memory, Order, User
from tests.test_payments import API, _approved, _checkout, paypal  # noqa: F401 (paypal is a fixture)


def test_receipt_says_paid_only_after_a_verified_capture(client, session, paypal):  # noqa: F811
    a = _approved(client)
    oid = a["order"]["id"]
    before = client.get(f"/api/v1/orders/{oid}/receipt").json()
    assert before["state"] == "approved" and before["completed_at"] is None and before["follow_up"]["items"] == []
    assert before["payment"]["capture_id"] is None

    body = {"order_id": oid, "paypal_order_id": _checkout(client, paypal, oid)}
    assert client.get(f"/api/v1/orders/{oid}/receipt").json()["state"] == "payment_pending"
    client.post(f"{API}/paypal/capture-order", json=body)

    r = client.get(f"/api/v1/orders/{oid}/receipt").json()
    assert r["state"] == "paid" and r["payment"]["verified"] and r["payment"]["capture_id"] and r["completed_at"]
    assert r["request"]["message"] and r["approval"]["approved"] and r["approval"]["version"] == a["order_version"]
    assert {"Consumer Buyer", "Procurement", "Financial Autopilot", "Post-Purchase"} <= {x["name"] for x in r["agents"]}
    assert r["research"]["excluded"] and any(i["alternatives"] for i in r["items"])  # what was ruled out, and why
    fu = r["follow_up"]["items"]
    assert len(fu) == len(r["items"]) and all(f["return_by"] and f["delivery"] is None for f in fu)  # no invented delivery

    # The agent ran exactly once, even if capture is called again.
    client.post(f"{API}/paypal/capture-order", json=body)
    assert session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "post_purchase")) == 1
    listed = client.get("/api/v1/orders").json()
    assert listed[0]["order_id"] == oid and listed[0]["state"] == "paid" and listed[0]["feedback_left"] == len(r["items"])


def test_purchase_feedback_is_checked_and_teaches(client, session, paypal):  # noqa: F811
    a = _approved(client)
    oid = a["order"]["id"]
    item = a["items"][0]["product"]
    fb = {"order_id": oid, "product_id": item["id"], "rating": 3, "didnt_work": "Wobbles", "reasons": ["durability"]}

    assert client.post("/api/v1/me/feedback", json=fb).status_code == 409  # not paid yet
    client.post(f"{API}/paypal/capture-order", json={"order_id": oid, "paypal_order_id": _checkout(client, paypal, oid)})

    theo = session.scalar(select(User).where(User.email.like("theo%")))
    assert client.post("/api/v1/me/feedback", json=fb, headers={"X-PersonalIQ-User": str(theo.id)}).status_code == 404
    assert client.post("/api/v1/me/feedback", json={**fb, "product_id": str(uuid.uuid4())}).status_code == 422
    assert client.post("/api/v1/me/feedback", json=fb).status_code == 201
    assert client.post("/api/v1/me/feedback", json=fb).status_code == 409  # once per item

    r = client.get(f"/api/v1/orders/{oid}/receipt").json()
    rated = next(f for f in r["follow_up"]["items"] if f["product_id"] == item["id"])
    assert rated["feedback"]["rating"] == 3
    lesson = session.scalar(select(Memory).where(Memory.memory_type == "lesson", Memory.content.contains(item["name"])))
    assert lesson is not None and lesson.source == "feedback"
