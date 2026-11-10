import uuid
from decimal import Decimal

from sqlalchemy import select

from app.agents import llm
from app.models import Order
from app.services.intent import parse_intent


def test_intent_reads_budget_currency_and_items():
    i = parse_intent("Help me set up my new apartment, budget ₹1.5 lakh", "INR")
    assert (i.template, i.budget) == ("apartment", Decimal("150000.00"))

    chair = parse_intent("Find a durable office chair under $200", "INR")  # a rupee user writing in dollars
    assert [n.need for n in chair.needs] == ["office_chair"]
    assert chair.budget == Decimal("16900.00") and "Converted from $200.00" in chair.budget_note

    assert parse_intent("a 13 gallon trash can for 2 people", "USD").budget is None  # not money


def test_apartment_workflow_runs_end_to_end(client, session):
    assert not llm.get_llm().available  # the LLM is stubbed out in tests (see conftest), fallbacks are used
    started = client.post("/api/v1/workflows", json={"message": "I'm moving next month, set up my new apartment"}).json()
    wf = client.get(f"/api/v1/workflows/{started['id']}").json()  # TestClient runs the background task first

    assert wf["status"] == "awaiting_approval", wf["message"]
    runs = {r["agent_name"]: r for r in wf["runs"]}
    assert set(runs) == {"supervisor_plan", "life_operations", "consumer_buyer", "procurement", "financial", "supervisor_verify"}
    assert all(r["status"] == "completed" for r in runs.values())
    # Procurement starts only after both parallel agents have finished.
    assert runs["procurement"]["started_at"] >= max(runs["life_operations"]["finished_at"], runs["consumer_buyer"]["finished_at"])

    # Budget came from Priya's saved "Apartment move" budget, in rupees; a proposed order was saved.
    assert "Apartment move" in runs["supervisor_plan"]["explanation"]
    order = session.get(Order, uuid.UUID(wf["result"]["order_id"]))
    assert order.status == "awaiting_approval" and order.currency == "INR" and order.total <= Decimal("169000")
    assert len(order.items) == len(wf["result"]["cart"]["lines"])


def test_workflow_blocks_or_asks_instead_of_guessing(client):
    blocked = client.post("/api/v1/workflows", json={"message": "Set up my new apartment for ₹10,000"}).json()
    wf = client.get(f"/api/v1/workflows/{blocked['id']}").json()
    assert wf["status"] == "blocked" and "at least" in wf["message"]

    unclear = client.post("/api/v1/workflows", json={"message": "hello there"}).json()
    wf = client.get(f"/api/v1/workflows/{unclear['id']}").json()
    assert wf["status"] == "needs_input" and "?" in wf["message"]


def test_named_items_are_the_only_must_haves(client):
    # "home office" brings a template (desk, chair, ...) but the user only asked for a chair.
    res = client.post("/api/v1/workflows", json={"message": "a chair for my home office, under ₹20,000"}).json()
    wf = client.get(f"/api/v1/workflows/{res['id']}").json()
    needs = {n["need"]: n["required"] for n in next(r for r in wf["runs"] if r["agent_name"] == "life_operations")["output"]["result"]["needs"]}
    assert needs["office_chair"] is True and needs["desk"] is False
    assert wf["status"] == "awaiting_approval"
