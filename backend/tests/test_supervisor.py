"""Supervisor decisions: recovery from real failures, bounded; crash retry; the policy gate."""

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.agents import consumer_buyer
from app.agents.supervisor import decide_recovery, policy_violations
from app.models import AgentRun, Budget, Order, User


def _fin_failed(limit: str, committed: str) -> dict:
    return {"status": "failed", "result": {"evaluation": {"limit": limit, "committed": committed, "budget_name": "Apartment move"}}}


def test_recovery_is_chosen_from_the_failure_and_bounded():
    ok_cart = {"status": "completed"}
    first = decide_recovery({"procurement": ok_cart, "financial": _fin_failed("169000", "69000")}, {}, "INR")
    assert first["strategy"] == "fit_remaining" and first["budget"] == "100000.00"

    second = decide_recovery({"procurement": {"status": "failed", "explanation": "Too little."}}, {"tried": ["fit_remaining"]}, "INR")
    assert second["strategy"] == "deeper_search"
    assert decide_recovery({"procurement": {"status": "failed"}}, {"tried": ["fit_remaining", "deeper_search"]}, "INR") is None  # bounded
    assert decide_recovery({"procurement": {"status": "failed"}}, {"tried": ["deeper_search"]}, "INR") is None  # never twice
    # Nothing committed yet: a financial failure isn't something rebuilding can fix.
    assert decide_recovery({"procurement": ok_cart, "financial": _fin_failed("169000", "0")}, {}, "INR") is None


def test_policy_gate():
    cart = {"total": "500.00", "currency": "INR", "lines": [{"product": {"id": "p2", "name": "Mystery lamp"}, "quantity": 1}]}
    v = policy_violations(cart, Decimal("400"), {"lamp": [{"product_id": "p1"}]}, "INR")
    assert any("over" in x for x in v) and any("Mystery lamp" in x for x in v)


def _run(client, message: str) -> dict:
    wf = client.post("/api/v1/workflows", json={"message": message}).json()
    return client.get(f"/api/v1/workflows/{wf['id']}").json()


def test_supervisor_rebuilds_the_cart_for_what_is_left_of_the_budget(client, session):
    priya = session.scalar(select(User).where(User.email.like("priya%")))
    budget = session.scalar(select(Budget).where(Budget.user_id == priya.id, Budget.name == "Apartment move"))
    # An earlier, already paid order used part of the Apartment move budget.
    session.add(Order(user_id=priya.id, budget_id=budget.id, status="paid", subtotal=Decimal("69000"), shipping=Decimal("0"),
                      tax=Decimal("0"), total=Decimal("69000"), currency="INR"))
    session.commit()

    wf = _run(client, "Set up my new apartment with the essentials")
    recover = [r for r in wf["runs"] if r["agent_name"] == "supervisor_recover"]
    assert recover and recover[0]["output"]["decision"]["strategy"] == "fit_remaining"
    assert "₹1,00,000.00 is left" in recover[0]["explanation"]
    assert wf["status"] == "awaiting_approval", wf["message"]
    order = session.get(Order, uuid.UUID(wf["result"]["order_id"]))
    assert order.total <= Decimal("100000")  # fits what's actually left


def test_a_crashed_agent_is_retried_once(client, session, monkeypatch):
    real, calls = consumer_buyer.run, []

    def flaky(task, s, ctx):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("catalog read timed out")
        return real(task, s, ctx)

    monkeypatch.setattr(consumer_buyer, "run", flaky)
    wf = _run(client, "Set up my new apartment with the essentials")
    assert wf["status"] == "awaiting_approval" and len(calls) == 2
    run = session.scalar(select(AgentRun).where(AgentRun.agent_name == "consumer_buyer"))
    assert run.output["attempts"] == 2 and "TimeoutError" in run.output["crashes"][0]


def test_when_nothing_works_it_stops_and_says_what_it_tried(client, session):
    priya = session.scalar(select(User).where(User.email.like("priya%")))
    budget = session.scalar(select(Budget).where(Budget.user_id == priya.id, Budget.name == "Apartment move"))
    session.add(Order(user_id=priya.id, budget_id=budget.id, status="paid", subtotal=Decimal("161815.82"), shipping=Decimal("0"),
                      tax=Decimal("0"), total=Decimal("161815.82"), currency="INR"))  # like the real demo: ₹7,184.18 left
    session.commit()

    wf = _run(client, "Set up my new apartment with the essentials")
    strategies = [r["output"]["decision"]["strategy"] for r in wf["runs"] if r["agent_name"] == "supervisor_recover"]
    assert strategies == ["fit_remaining", "deeper_search"]  # both tried, once each, then it stops
    assert wf["status"] == "blocked" and "I also tried" in wf["message"]
    assert "order_id" not in wf["result"]  # nothing proposed
