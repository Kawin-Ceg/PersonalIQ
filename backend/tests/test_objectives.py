"""Life Operations task plans: dependencies, dates worked backwards, and progress from real events."""

from datetime import date

from sqlalchemy import select

from app.agents.life_operations import task_plan
from app.models import User
from tests.test_payments import API, _approved, _checkout, paypal  # noqa: F401 (paypal is a fixture)


def test_plan_works_backwards_from_the_target_date():
    tasks, warnings = task_plan("apartment", date(2026, 12, 10), date(2026, 11, 10))
    by = {t["key"]: t for t in tasks}
    assert by["pay"]["due_on"] == "2026-12-01" and by["deliveries"]["due_on"] == "2026-12-08"  # 7-day delivery + 2-day buffer
    assert by["movers"]["external"] and by["movers"]["tracking"] == "manual"  # can't be booked, so it's yours
    assert "address" in by["pay"]["depends_on"] and by["cart"]["depends_on"] == ["needs", "research"]
    assert "assumes 7-day delivery" in warnings[0]

    _, tight = task_plan("apartment", date(2026, 11, 14), date(2026, 11, 10))
    assert tight[0].startswith("Tight timeline")
    kitchen, none = task_plan("kitchen", None, date(2026, 11, 10))
    assert all(t["due_on"] is None and not t["external"] for t in kitchen) and none == []


def test_tasks_track_real_events_and_only_manual_ones_can_be_ticked(client, session, paypal):  # noqa: F811
    a = _approved(client)
    wf = client.get(f"/api/v1/workflows/{a['workflow_id']}").json()
    summary = next(w for w in client.get("/api/v1/workflows").json() if w["id"] == wf["id"])
    obj_id = summary["objective_id"]

    def tasks():
        return {t["key"]: t for t in client.get(f"/api/v1/objectives/{obj_id}").json()["tasks"]}

    t = tasks()
    assert all(t[k]["state"] == "done" for k in ("needs", "research", "cart", "budget", "approve"))
    assert t["pay"]["state"] == "waiting" and "Make sure deliveries go to the new address" in t["pay"]["waiting_on"]

    url = f"/api/v1/objectives/{obj_id}/tasks"
    assert client.post(f"{url}/{t['pay']['id']}", json={"done": True}).status_code == 409  # only PayPal can tick this
    assert client.post(f"{url}/{t['deliveries']['id']}", json={"done": True}).status_code == 409  # waits on payment
    theo = session.scalar(select(User).where(User.email.like("theo%")))
    assert client.get(f"/api/v1/objectives/{obj_id}", headers={"X-PersonalIQ-User": str(theo.id)}).status_code == 404

    client.post(f"{url}/{t['address']['id']}", json={"done": True})
    oid = a["order"]["id"]
    client.post(f"{API}/paypal/capture-order", json={"order_id": oid, "paypal_order_id": _checkout(client, paypal, oid)})
    t = tasks()
    assert t["pay"]["state"] == "done" and t["deliveries"]["state"] == "ready" and t["returns"]["due_on"]
    view = client.post(f"{url}/{t['deliveries']['id']}", json={"done": True}).json()
    states = {x["key"]: x["state"] for x in view["tasks"]}
    assert view["progress"]["done"] == 8 and states["returns"] == "ready" and states["feedback"] == "ready"
