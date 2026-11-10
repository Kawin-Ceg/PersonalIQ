"""PayPal payments against a FAKE PayPal (httpx.MockTransport), so the real client, auth, order and
capture code runs without the network. The live Sandbox check is manual: see docs/PAYMENT_FLOW.md."""

import json
import re
import uuid
from collections import defaultdict
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.api.routes.payments import paypal_client
from app.core.config import get_settings
from app.integrations.paypal import orders as pp_orders
from app.integrations.paypal.client import PayPalClient
from app.integrations.paypal.exceptions import PayPalAuthError
from app.main import app
from app.models import Approval, Order, OrderItem, PaymentEvent, Transaction, User
from app.services.order_state import InvalidTransition, can_transition, transition
from tests.test_approvals import _ready_approval

API = "/api/v1/payments"
SANDBOX = "https://api-m.sandbox.paypal.com"


class FakePayPal:
    """Just enough of PayPal Orders v2: token, create, get, capture (idempotent by PayPal-Request-Id), webhook verify."""

    def __init__(self, secret_ok: bool = True):
        self.secret_ok = secret_ok
        self.orders: dict[str, dict] = {}
        self.by_request: dict[str, dict] = {}
        self.calls: dict[str, int] = defaultdict(int)
        self.capture_ids: list[str] = []
        self.capture_mode = "complete"  # complete | short | pending | timeout_before | timeout_after
        self.webhook_valid = True
        self.last_create: dict | None = None

    def client(self) -> PayPalClient:
        return PayPalClient("test-id", "test-secret", SANDBOX, transport=httpx.MockTransport(self.handle))

    def buyer_approves(self, oid: str) -> None:
        self.orders[oid]["status"] = "APPROVED"

    def _capture(self, oid: str) -> dict:
        order = self.orders[oid]
        pu = order["purchase_units"][0]
        amount = dict(pu["amount"])
        if self.capture_mode == "short":
            amount["value"] = f"{Decimal(amount['value']) - 1:.2f}"
        cap = {"id": f"CAP{oid[4:]}", "status": "PENDING" if self.capture_mode == "pending" else "COMPLETED",
               "amount": amount, "custom_id": pu["custom_id"]}
        if self.capture_mode == "pending":
            cap["status_details"] = {"reason": "PENDING_REVIEW"}
        order["status"] = "COMPLETED"
        pu["payments"] = {"captures": [cap]}
        return order

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, rid = request.url.path, request.headers.get("PayPal-Request-Id")
        if path == "/v1/oauth2/token":
            self.calls["token"] += 1
            if not self.secret_ok:
                return httpx.Response(401, json={"error": "invalid_client", "error_description": "Client Authentication failed"})
            return httpx.Response(200, json={"access_token": "fake-token", "token_type": "Bearer", "expires_in": 32400})
        assert request.headers["Authorization"] == "Bearer fake-token"

        if path == "/v1/notifications/verify-webhook-signature":
            self.calls["verify"] += 1
            body = json.loads(request.content)  # the raw event must still make valid JSON
            assert body["webhook_id"] == "WH-TEST" and body["webhook_event"]["id"]
            return httpx.Response(200, json={"verification_status": "SUCCESS" if self.webhook_valid else "FAILURE"})

        if request.method == "POST" and path == "/v2/checkout/orders":
            self.calls["create"] += 1
            if rid in self.by_request:
                return httpx.Response(200, json=self.by_request[rid])
            body = self.last_create = json.loads(request.content)
            pu = body["purchase_units"][0]
            oid = f"FAKE{len(self.orders) + 1:013d}"
            self.orders[oid] = self.by_request[rid] = {
                "id": oid, "status": "PAYER_ACTION_REQUIRED",
                "purchase_units": [{"reference_id": pu["reference_id"], "custom_id": pu["custom_id"], "amount": {
                    "currency_code": pu["amount"]["currency_code"], "value": pu["amount"]["value"]}}],
            }
            return httpx.Response(201, json=self.orders[oid])

        m = re.fullmatch(r"/v2/checkout/orders/(\w+)(/capture)?", path)
        assert m, path
        oid = m.group(1)
        if oid not in self.orders:
            return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND", "message": "not found", "details": [{"issue": "INVALID_RESOURCE_ID"}]})
        if not m.group(2):
            self.calls["get"] += 1
            return httpx.Response(200, json=self.orders[oid])

        self.calls["capture"] += 1
        self.capture_ids.append(rid)
        if rid in self.by_request:
            return httpx.Response(201, json=self.by_request[rid])
        if self.orders[oid]["status"] == "COMPLETED":
            return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "message": "x", "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]})
        if self.orders[oid]["status"] != "APPROVED":
            return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "message": "x", "details": [{"issue": "ORDER_NOT_APPROVED"}]})
        if self.capture_mode == "timeout_before":
            raise httpx.ReadTimeout("timed out", request=request)  # never reached PayPal's ledger
        self.by_request[rid] = self._capture(oid)
        if self.capture_mode == "timeout_after":
            raise httpx.ReadTimeout("timed out", request=request)  # captured, but the answer was lost
        return httpx.Response(201, json=self.by_request[rid])


@pytest.fixture
def paypal(client, monkeypatch):
    # Pin USD whatever backend/.env says, so the INR -> USD conversion path stays tested.
    monkeypatch.setattr(get_settings(), "paypal_currency", "USD")
    fake = FakePayPal()
    pp = fake.client()
    app.dependency_overrides[paypal_client] = lambda: pp
    return fake


def _approved(client) -> dict:
    a = _ready_approval(client)
    for item in a["items"]:
        if item["risk"]["level"] == "needs_decision":
            client.post(f"/api/v1/approvals/{a['id']}/items/{item['id']}", json={"action": "keep"})
    a = client.post(f"/api/v1/approvals/{a['id']}/approve", json={"order_hash": a["order_hash"]}).json()
    assert a["status"] == "approved"
    return a


def _checkout(client, paypal, order_id: str) -> str:
    r = client.post(f"{API}/paypal/create-order", json={"order_id": order_id})
    assert r.status_code == 200, r.text
    paypal.buyer_approves(r.json()["paypal_order_id"])
    return r.json()["paypal_order_id"]


def test_sandbox_flow_charges_the_approved_amount_once(client, session, paypal):
    a = _approved(client)
    oid = a["order"]["id"]
    assert a["charge"]["currency"] == "USD" and a["order"]["currency"] == "INR"  # shown before approving

    created = client.post(f"{API}/paypal/create-order", json={"order_id": oid}).json()
    assert created["order_status"] == "awaiting_buyer_checkout"
    assert created["amount"] == a["charge"]["total"] and created["currency"] == "USD"
    sent = paypal.last_create["purchase_units"][0]
    assert sent["amount"]["value"] == a["charge"]["total"] and sent["reference_id"] == oid
    assert sum(Decimal(i["unit_amount"]["value"]) * int(i["quantity"]) for i in sent["items"]) == Decimal(sent["amount"]["breakdown"]["item_total"]["value"])

    # Asking again reuses the open PayPal order. Closing the PayPal window charges nothing.
    again = client.post(f"{API}/paypal/create-order", json={"order_id": oid}).json()
    assert again["paypal_order_id"] == created["paypal_order_id"] and paypal.calls["create"] == 1
    body = {"order_id": oid, "paypal_order_id": created["paypal_order_id"]}
    assert client.post(f"{API}/paypal/checkout-cancelled", json=body).json()["order_status"] == "awaiting_buyer_checkout"

    paypal.buyer_approves(created["paypal_order_id"])
    paid = client.post(f"{API}/paypal/capture-order", json=body).json()
    assert paid["order_status"] == "paid" and paid["verified"] and paid["capture_id"]

    dup = client.post(f"{API}/paypal/capture-order", json=body).json()
    assert dup["already_captured"] and paypal.calls["capture"] == 1  # no second capture
    ledger = session.scalars(select(Transaction).where(Transaction.source == "paypal")).all()
    assert sum(t.amount for t in ledger) == Decimal(a["order"]["total"])
    view = client.get(f"/api/v1/approvals/{a['id']}").json()
    assert any(e["title"] == "Paid, verified with PayPal" for e in view["timeline"])


def test_create_order_refuses_what_it_should(client, session, paypal):
    pending = _ready_approval(client)
    oid = pending["order"]["id"]
    r = client.post(f"{API}/paypal/create-order", json={"order_id": oid})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_approved"

    for item in pending["items"]:
        if item["risk"]["level"] == "needs_decision":
            client.post(f"/api/v1/approvals/{pending['id']}/items/{item['id']}", json={"action": "keep"})
    client.post(f"/api/v1/approvals/{pending['id']}/approve", json={"order_hash": pending["order_hash"]})

    assert client.post(f"{API}/paypal/create-order", json={"order_id": str(uuid.uuid4())}).status_code == 404
    theo = session.scalar(select(User).where(User.email.like("theo%")))
    other = client.post(f"{API}/paypal/create-order", json={"order_id": oid}, headers={"X-PersonalIQ-User": str(theo.id)})
    assert other.status_code == 404  # someone else's order
    sneaky = client.post(f"{API}/paypal/create-order", json={"order_id": oid, "amount": "1.00", "currency": "USD"})
    assert sneaky.status_code == 422  # the client can't name an amount
    assert paypal.calls["create"] == 0

    assert client.post(f"{API}/orders/{oid}/cancel").json()["order_status"] == "cancelled"
    assert client.post(f"{API}/paypal/create-order", json={"order_id": oid}).status_code == 409


def test_order_changed_after_approval_needs_a_new_approval(client, session, paypal):
    a = _approved(client)
    order = session.get(Order, uuid.UUID(a["order"]["id"]))
    item: OrderItem = order.items[0]
    item.quantity += 1  # totals stay consistent, but this isn't what the user approved
    item.line_total = item.unit_price * item.quantity
    order.subtotal += item.unit_price
    order.total += item.unit_price
    session.commit()

    r = client.post(f"{API}/paypal/create-order", json={"order_id": a["order"]["id"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "reapproval_required"
    assert session.get(Approval, uuid.UUID(a["id"])).status == "invalidated"
    new = session.get(Approval, uuid.UUID(r.json()["detail"]["approval_id"]))
    assert new.status == "pending" and new.order_version == a["order_version"] + 1
    assert order.status == "awaiting_approval" and paypal.calls["create"] == 0


def test_capture_timeout_is_checked_with_paypal_not_assumed(client, session, paypal):
    a = _approved(client)
    body = {"order_id": a["order"]["id"], "paypal_order_id": _checkout(client, paypal, a["order"]["id"])}

    paypal.capture_mode = "timeout_before"  # PayPal never captured
    r = client.post(f"{API}/paypal/capture-order", json=body).json()
    assert r["order_status"] == "awaiting_buyer_checkout" and not r["verified"] and paypal.calls["get"] >= 1

    paypal.capture_mode = "timeout_after"  # PayPal captured, the answer was lost
    r = client.post(f"{API}/paypal/capture-order", json=body).json()
    assert r["order_status"] == "paid" and r["verified"]
    assert len(set(paypal.capture_ids)) == 1  # every retry reused the same PayPal-Request-Id


def test_capture_for_the_wrong_amount_is_not_paid(client, session, paypal):
    a = _approved(client)
    paypal.capture_mode = "short"
    body = {"order_id": a["order"]["id"], "paypal_order_id": _checkout(client, paypal, a["order"]["id"])}
    r = client.post(f"{API}/paypal/capture-order", json=body).json()
    assert r["order_status"] == "reconciliation_required" and not r["verified"] and "approved amount" in r["message"]
    assert session.scalar(select(func.count()).select_from(Transaction).where(Transaction.source == "paypal")) == 0


def test_webhook_is_verified_and_processed_once(client, session, paypal, monkeypatch):
    monkeypatch.setattr(get_settings(), "paypal_webhook_id", "WH-TEST")
    a = _approved(client)
    ppid = _checkout(client, paypal, a["order"]["id"])
    capture = paypal._capture(ppid)["purchase_units"][0]["payments"]["captures"][0]  # captured, but we never heard back
    event = {"id": "WH-EVT-1", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource_type": "capture",
             "resource": {**capture, "supplementary_data": {"related_ids": {"order_id": ppid}}}}
    headers = {"paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
               "paypal-transmission-id": "t1", "paypal-transmission-sig": "sig", "paypal-transmission-time": "2026-11-10T10:00:00Z"}
    send = lambda h: client.post(f"{API}/paypal/webhook", content=json.dumps(event), headers=h)  # noqa: E731

    assert send({}).status_code == 400  # no signature headers
    paypal.webhook_valid = False
    assert send(headers).status_code == 400
    assert session.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.provider_event_id == "WH-EVT-1")) == 0

    paypal.webhook_valid = True
    assert send(headers).json()["status"] == "processed"
    assert send(headers).json()["status"] == "duplicate"
    assert session.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.provider_event_id == "WH-EVT-1")) == 1
    order = session.get(Order, uuid.UUID(a["order"]["id"]))
    session.refresh(order)
    assert order.status == "paid"  # confirmed by asking PayPal, not by trusting the payload


def test_bad_credentials_token_cache_and_state_machine():
    with pytest.raises(PayPalAuthError):
        pp_orders.get_order(FakePayPal(secret_ok=False).client(), "FAKE1")

    fake = FakePayPal()
    pp = fake.client()
    for _ in range(3):
        with pytest.raises(Exception):
            pp_orders.get_order(pp, "MISSING")  # 404s, but each one is authenticated
    assert fake.calls["token"] == 1  # token cached

    assert not can_transition("approved", "paid") and not can_transition("paid", "capturing")
    with pytest.raises(InvalidTransition):
        transition(Order(status="awaiting_approval"), "capturing")
