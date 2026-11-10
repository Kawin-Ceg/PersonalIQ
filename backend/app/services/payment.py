"""Payments: create a PayPal order from an approved order, capture it, verify it, reconcile it.

Rules this module enforces:
- The amount always comes from the approved database order (see settlement.py), never from the browser.
- The approval must still match the order exactly (fingerprint, version, arithmetic, catalog prices).
  If anything changed, the approval is invalidated and the user approves the new version.
- Only one capture can run per order (atomic status claim + PayPal-Request-Id).
- PAID is set only after PayPal's own response shows a COMPLETED capture for the right amount,
  currency and internal order reference.
- A timeout means "unknown": we ask PayPal what happened before doing anything else.
"""

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.paypal import capture as pp_capture
from app.integrations.paypal import orders as pp_orders
from app.integrations.paypal.client import PayPalClient
from app.integrations.paypal.exceptions import (
    PayPalAPIError, PayPalAuthError, PayPalConfigError, PayPalError, PayPalTimeout, PayPalUnavailable,
)
from app.integrations.paypal.schemas import PayPalCapture, PayPalOrder, WebhookEvent, strip_personal_data
from app.integrations.paypal.webhooks import HANDLED_EVENTS, signature_fields, verify_signature
from app.models import Approval, AuditLog, Order, Payment, PaymentEvent, Product, Transaction, User
from app.services.approval import _aware, _now, _recompute, _set_workflow, _workflow, audit, order_hash, request_approval
from app.services.fx import convert, fmt
from app.services.order_state import InvalidTransition, OrderStatus, can_transition, claim, transition
from app.services.settlement import SettlementError, arithmetic_problems, charge_for, charge_request

S = OrderStatus
PAYMENT_WINDOW = timedelta(hours=24)  # an approval must be paid within 24 h of approving
STUCK_CAPTURE = timedelta(seconds=60)  # a capture still "running" after this can be reconciled
OPEN_PAYPAL_STATUSES = {"CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"}
CENT = Decimal("0.01")


class PaymentError(Exception):
    """Refusal with a machine code, a plain message and an HTTP status."""

    def __init__(self, code: str, message: str, status: int = 409, extra: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra or {}


def _paypal_failure(e: PayPalError) -> PaymentError:
    if isinstance(e, PayPalConfigError):
        return PaymentError("paypal_not_configured", str(e), 503)
    if isinstance(e, PayPalAuthError):
        return PaymentError("paypal_auth", "PayPal rejected the app's credentials, so nothing was sent. Check PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.", 502)
    if isinstance(e, PayPalUnavailable):
        return PaymentError("paypal_unavailable", "Couldn't reach PayPal. Nothing was charged. Try again.", 503)
    if isinstance(e, PayPalTimeout):
        return PaymentError("paypal_timeout", "PayPal didn't answer in time.", 504)
    assert isinstance(e, PayPalAPIError)
    debug = f" (PayPal debug id {e.debug_id})" if e.debug_id else ""
    if e.has_issue("CURRENCY_NOT_SUPPORTED") or e.has_issue("UNSUPPORTED_PAYEE_CURRENCY"):
        return PaymentError("paypal_currency", f"PayPal won't accept this currency for the Sandbox merchant account. "
                            f"See 'Currency' in docs/PAYMENT_FLOW.md{debug}.", 502)
    issue = f" [{', '.join(e.issues)}]" if e.issues else ""
    return PaymentError("paypal_error", f"PayPal refused{issue}: {e.message}{debug}", 502)


# ---------- lookups ----------


def _own_order(session: Session, user: User, order_id: uuid.UUID) -> Order:
    order = session.get(Order, order_id)
    if order is None or order.user_id != user.id:  # someone else's order looks the same as a missing one
        raise PaymentError("not_found", "Order not found.", 404)
    return order


def _approved_approval(session: Session, order: Order) -> Approval | None:
    return session.scalar(
        select(Approval).where(Approval.order_id == order.id, Approval.status == "approved").order_by(Approval.decided_at.desc()).limit(1)
    )


def _payments(session: Session, order: Order) -> list[Payment]:
    return list(session.scalars(select(Payment).where(Payment.order_id == order.id).order_by(Payment.attempt)))


def _latest_payment(session: Session, order: Order) -> Payment | None:
    pays = _payments(session, order)
    return pays[-1] if pays else None


def _move(order: Order, target: OrderStatus) -> None:
    """Transition, going through reconciliation_required when PayPal reports an outcome we didn't start."""
    if order.status == target:
        return
    if not can_transition(order.status, target) and can_transition(order.status, S.RECONCILIATION_REQUIRED) \
            and can_transition(S.RECONCILIATION_REQUIRED, target):
        transition(order, S.RECONCILIATION_REQUIRED)
    transition(order, target)


def _record_paypal(session: Session, pay: Payment, kind: str, body: dict) -> None:
    """Keep every PayPal response that changed a payment, minus payer details. Rows are never updated."""
    session.add(PaymentEvent(
        payment_id=pay.id, provider_event_id=f"api-{uuid.uuid4()}", event_type=f"API.{kind}.{body.get('status', 'UNKNOWN')}",
        payload=strip_personal_data(body),
    ))


# ---------- approval checks ----------


def _require_reapproval(session: Session, user: User, order: Order, approval: Approval, reason: str) -> None:
    """The order (or a price) changed after approval: void that approval and ask again for the current version."""
    for item in order.items:
        p = session.get(Product, item.product_id)
        item.unit_price = convert(p.price, p.currency, order.currency)
        item.line_total = (item.unit_price * item.quantity).quantize(CENT)
    session.flush()
    _recompute(session, order)
    order.version += 1
    approval.status = "invalidated"
    for pay in _payments(session, order):
        if pay.status in ("creating", "created"):
            pay.status, pay.failure_reason = "replaced", "The order changed before payment."
    transition(order, S.AWAITING_APPROVAL)
    audit(session, user.id, "system", "approval_invalidated", order.id, {"approval_id": str(approval.id), "reason": reason, "version": order.version})
    wf = _workflow(session, order)
    new = request_approval(session, user, order, wf, approval.details.get("confirmed"), actor="system")
    if wf:
        outcome = wf.state.get("outcome") or {}
        wf.state = {**wf.state, "outcome": {**outcome, "result": {**(outcome.get("result") or {}), "approval_id": str(new.id)}}}
    _set_workflow(session, order, "awaiting_approval", f"{reason} Please approve the updated order.")
    session.commit()
    raise PaymentError("reapproval_required", f"{reason} Your earlier approval no longer applies. Review and approve the updated order.",
                       409, {"approval_id": str(new.id)})


def _check_approval(session: Session, user: User, order: Order, *, enforce_window: bool = True) -> Approval:
    approval = _approved_approval(session, order)
    if approval is None:
        raise PaymentError("not_approved", "This order hasn't been approved.", 409)
    if enforce_window and _aware(approval.decided_at) + PAYMENT_WINDOW <= _now():
        approval.status = "expired"
        transition(order, S.EXPIRED)
        audit(session, user.id, "system", "payment_window_expired", order.id, {"approval_id": str(approval.id)})
        _set_workflow(session, order, "expired", "The approval expired before payment. Nothing was charged.")
        session.commit()
        raise PaymentError("expired", "This approval is more than 24 hours old. Start the request again for a fresh order.", 410)
    if order.version != approval.order_version or order_hash(order) != approval.order_hash:
        _require_reapproval(session, user, order, approval, "The order changed after you approved it.")
    if problems := arithmetic_problems(order):
        _require_reapproval(session, user, order, approval, f"The order's totals didn't add up ({problems[0]}).")
    for item in order.items:
        p = session.get(Product, item.product_id)
        if convert(p.price, p.currency, order.currency) != item.unit_price:
            _require_reapproval(session, user, order, approval, f"The price of {p.name} changed.")
    return approval


# ---------- create ----------


def create_paypal_order(session: Session, user: User, order_id: uuid.UUID, paypal: PayPalClient) -> dict:
    order = _own_order(session, user, order_id)
    if order.status == S.PAID:
        raise PaymentError("already_paid", "This order is already paid.", 409)
    if order.status not in (S.APPROVED, S.AWAITING_BUYER_CHECKOUT):
        raise PaymentError("not_approved", f"This order can't be paid right now (it is {order.status.replace('_', ' ')}).", 409)
    approval = _check_approval(session, user, order)

    if order.status == S.AWAITING_BUYER_CHECKOUT:
        # A PayPal order already exists. Reuse it if PayPal still considers it open.
        current = _latest_payment(session, order)
        if current and current.status == "created" and current.provider_order_id:
            try:
                ppo, _ = pp_orders.get_order(paypal, current.provider_order_id)
            except PayPalAPIError as e:
                if e.status_code != 404:
                    raise _paypal_failure(e)
                ppo = None
            except PayPalError as e:
                raise _paypal_failure(e)
            if ppo and ppo.status in OPEN_PAYPAL_STATUSES:
                return _created_out(order, current)
            if ppo and ppo.status == "COMPLETED":
                raise PaymentError("check_payment", "PayPal says this order was already paid. Use 'Check with PayPal'.", 409)
            current.status, current.paypal_status = "replaced", ppo.status if ppo else "NOT_FOUND"
            current.failure_reason = "PayPal no longer has this order open; a new one replaces it."

    try:
        req = charge_request(session, order, description=f"PersonalIQ order {str(order.id)[:8]} (v{order.version})")
    except SettlementError as e:
        raise PaymentError("currency_not_supported", str(e), 422)
    attempt = (session.scalar(select(func.max(Payment.attempt)).where(Payment.order_id == order.id)) or 0) + 1
    pay = Payment(
        order_id=order.id, approval_id=approval.id, attempt=attempt, amount=req.total, currency=req.currency,
        request_id=f"piq-{order.id}-{attempt}", status="creating",
    )
    session.add(pay)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise PaymentError("busy", "A PayPal order is already being created for this order. Try again in a moment.", 409)

    try:
        ppo, body = pp_orders.create_order(paypal, req, pay.request_id)
    except PayPalError as e:
        # An unapproved PayPal order can't move money, so a failed or uncertain create is safe to just retry.
        pay.status, pay.failure_reason = "failed", str(e)[:500]
        audit(session, user.id, "system", "paypal_order_failed", order.id, {"payment_id": str(pay.id), "reason": _paypal_failure(e).message})
        session.commit()
        raise _paypal_failure(e)

    pu = ppo.purchase_units[0] if ppo.purchase_units else None
    if ppo.status not in OPEN_PAYPAL_STATUSES or (pu and pu.amount and (pu.amount.value != req.total or pu.amount.currency_code != req.currency)):
        pay.status, pay.failure_reason = "failed", f"PayPal returned an unexpected order ({ppo.status})."
        session.commit()
        raise PaymentError("paypal_mismatch", "PayPal returned an order that doesn't match. Nothing was charged.", 502)

    pay.provider_order_id, pay.paypal_status, pay.status = ppo.id, ppo.status, "created"
    _record_paypal(session, pay, "CREATE", body)
    transition(order, S.PAYPAL_ORDER_CREATED)
    audit(session, user.id, "system", "paypal_order_created", order.id, {
        "payment_id": str(pay.id), "paypal_order_id": ppo.id, "charged": fmt(req.total, req.currency),
    })
    transition(order, S.AWAITING_BUYER_CHECKOUT)
    session.commit()
    return _created_out(order, pay)


def _created_out(order: Order, pay: Payment) -> dict:
    return {"payment_id": str(pay.id), "paypal_order_id": pay.provider_order_id, "amount": f"{pay.amount:.2f}",
            "currency": pay.currency, "order_status": order.status}


# ---------- capture ----------


def _capture_request_id(session: Session, order: Order, pay: Payment) -> str:
    """Same id for retries of the same attempt (PayPal dedupes). A new id only after a card was declined."""
    declines = sum(
        1 for e in session.scalars(select(AuditLog).where(AuditLog.entity == "order", AuditLog.entity_id == str(order.id), AuditLog.action == "capture_declined"))
        if e.detail.get("payment_id") == str(pay.id)
    )
    return f"{pay.request_id}-capture-{declines}"


def capture(session: Session, user: User, order_id: uuid.UUID, paypal_order_id: str, paypal: PayPalClient) -> dict:
    order = _own_order(session, user, order_id)
    pay = session.scalar(select(Payment).where(Payment.order_id == order.id, Payment.provider_order_id == paypal_order_id))
    if pay is None:
        raise PaymentError("unknown_paypal_order", "That PayPal order doesn't belong to this order.", 404)
    if order.status == S.PAID:
        return {**payment_view(session, order), "already_captured": True}  # idempotent: no second capture
    if order.status == S.CAPTURING:
        raise PaymentError("capture_in_progress", "This payment is already being captured.", 409)
    if order.status == S.RECONCILIATION_REQUIRED:
        return reconcile(session, order, pay, paypal)
    if order.status != S.AWAITING_BUYER_CHECKOUT or pay.status != "created":
        raise PaymentError("not_capturable", f"This order can't be captured (it is {order.status.replace('_', ' ')}).", 409)

    approval = session.get(Approval, pay.approval_id)
    if approval.status != "approved":
        raise PaymentError("not_approved", "The approval for this payment is no longer valid.", 409)
    # Approved within the window when the PayPal order was made; the buyer may finish checkout a bit later.
    _check_approval(session, user, order, enforce_window=False)
    charge = charge_for(order)
    if charge.total != pay.amount or charge.currency != pay.currency:
        _require_reapproval(session, user, order, approval, "The amount to charge changed.")

    if not claim(session, order, S.AWAITING_BUYER_CHECKOUT, S.CAPTURING):
        raise PaymentError("capture_in_progress", "This payment is already being captured.", 409)
    pay.status = "capturing"
    audit(session, user.id, "system", "capture_started", order.id, {"payment_id": str(pay.id), "paypal_order_id": paypal_order_id})
    session.commit()

    try:
        ppo, body = pp_capture.capture_order(paypal, paypal_order_id, _capture_request_id(session, order, pay))
    except PayPalTimeout:
        transition(order, S.RECONCILIATION_REQUIRED)
        pay.status, pay.failure_reason = "unknown", "PayPal didn't answer the capture in time. Checking what happened."
        audit(session, user.id, "system", "capture_uncertain", order.id, {"payment_id": str(pay.id)})
        session.commit()
        return reconcile(session, order, pay, paypal)
    except (PayPalAuthError, PayPalUnavailable, PayPalConfigError) as e:
        # The capture was never sent, so going back is safe.
        transition(order, S.AWAITING_BUYER_CHECKOUT)
        pay.status = "created"
        session.commit()
        raise _paypal_failure(e)
    except PayPalAPIError as e:
        return _capture_refused(session, user, order, pay, e, paypal)

    _record_paypal(session, pay, "CAPTURE", body)
    return _apply(session, order, pay, ppo)


def _capture_refused(session: Session, user: User, order: Order, pay: Payment, e: PayPalAPIError, paypal: PayPalClient) -> dict:
    if e.has_issue("ORDER_ALREADY_CAPTURED") or e.status_code >= 500:
        transition(order, S.RECONCILIATION_REQUIRED)
        pay.status = "unknown"
        session.commit()
        return reconcile(session, order, pay, paypal)
    buyer_issue = next((i for i in ("INSTRUMENT_DECLINED", "PAYER_ACTION_REQUIRED", "ORDER_NOT_APPROVED") if e.has_issue(i)), None)
    if buyer_issue:
        transition(order, S.AWAITING_BUYER_CHECKOUT)
        pay.status = "created"
        audit(session, user.id, "system", "capture_declined", order.id, {"payment_id": str(pay.id), "issue": buyer_issue})
        session.commit()
        code = "instrument_declined" if buyer_issue == "INSTRUMENT_DECLINED" else "buyer_action_required"
        msg = "PayPal declined that payment method. Choose another one." if code == "instrument_declined" else "Finish approving the payment in PayPal first."
        raise PaymentError(code, msg, 422)
    transition(order, S.FAILED)
    pay.status, pay.failure_reason = "failed", f"{e.name}: {e.message}"[:500]
    audit(session, user.id, "system", "payment_failed", order.id, {"payment_id": str(pay.id), "reason": e.message})
    _set_workflow(session, order, "failed", "PayPal refused the payment. Nothing was charged.")
    session.commit()
    raise _paypal_failure(e)


# ---------- verification ----------


def _verify(order: Order, pay: Payment, ppo: PayPalOrder, cap: PayPalCapture, n_captures: int) -> list[str]:
    problems = []
    if ppo.id != pay.provider_order_id:
        problems.append("PayPal order id doesn't match")
    if n_captures != 1:
        problems.append(f"expected one capture, PayPal shows {n_captures}")
    if cap.amount is None or cap.amount.currency_code != pay.currency:
        problems.append(f"currency isn't {pay.currency}")
    elif cap.amount.value != pay.amount:
        problems.append(f"captured {cap.amount.value} but the approved amount is {pay.amount}")
    refs = {pu.reference_id for pu in ppo.purchase_units} | {pu.custom_id for pu in ppo.purchase_units} | {cap.custom_id}
    if str(order.id) not in refs:
        problems.append("the internal order reference is missing")
    return problems


def _apply(session: Session, order: Order, pay: Payment, ppo: PayPalOrder) -> dict:
    """Move our records to whatever PayPal's own response proves. Never further."""
    if order.status == S.PAID:
        return payment_view(session, order)
    pay.paypal_status = ppo.status
    caps = ppo.captures()
    actor = "system"

    if not caps:
        if ppo.status in OPEN_PAYPAL_STATUSES:
            # Nothing captured: the buyer can (re)try.
            _move(order, S.AWAITING_BUYER_CHECKOUT)
            pay.status, pay.failure_reason = "created", ""
            audit(session, order.user_id, actor, "payment_not_captured", order.id, {"payment_id": str(pay.id), "paypal_status": ppo.status})
        elif ppo.status == "VOIDED":
            _move(order, S.AWAITING_BUYER_CHECKOUT)
            pay.status, pay.failure_reason = "replaced", "PayPal voided this checkout. Pay again to start a new one."
            audit(session, order.user_id, actor, "paypal_order_voided", order.id, {"payment_id": str(pay.id)})
        else:  # COMPLETED with no capture shown: can't confirm anything
            _move(order, S.RECONCILIATION_REQUIRED)
            pay.status, pay.failure_reason = "unknown", f"PayPal shows the order as {ppo.status} without a capture."
        session.commit()
        return payment_view(session, order)

    cap = caps[0]
    pay.provider_capture_id, pay.capture_status = cap.id, cap.status
    problems = _verify(order, pay, ppo, cap, len(caps))

    if cap.status == "COMPLETED" and not problems:
        _mark_paid(session, order, pay, cap)
    elif cap.status == "COMPLETED":
        _move(order, S.RECONCILIATION_REQUIRED)
        pay.status, pay.failure_reason = "mismatch", "; ".join(problems)
        audit(session, order.user_id, actor, "payment_mismatch", order.id, {"payment_id": str(pay.id), "capture_id": cap.id, "problems": problems})
        _set_workflow(session, order, "reconciliation_required", "PayPal's capture doesn't match the approved order. It needs checking; it is not marked paid.")
    elif cap.status == "PENDING":
        _move(order, S.RECONCILIATION_REQUIRED)
        reason = cap.status_details.reason if cap.status_details and cap.status_details.reason else "no reason given"
        pay.status, pay.failure_reason = "pending", f"PayPal is holding the payment ({reason})."
        audit(session, order.user_id, actor, "payment_pending", order.id, {"payment_id": str(pay.id), "capture_id": cap.id, "reason": reason})
    elif cap.status in ("DECLINED", "FAILED"):
        _move(order, S.FAILED)
        pay.status, pay.failure_reason = "failed", f"PayPal {cap.status.lower()} the capture."
        audit(session, order.user_id, actor, "payment_failed", order.id, {"payment_id": str(pay.id), "capture_id": cap.id, "reason": pay.failure_reason})
        _set_workflow(session, order, "failed", "PayPal declined the payment. Nothing was charged.")
    else:  # REFUNDED / PARTIALLY_REFUNDED: outside this build
        _move(order, S.RECONCILIATION_REQUIRED)
        pay.status, pay.failure_reason = "unknown", f"PayPal shows the capture as {cap.status}."
    session.commit()
    return payment_view(session, order)


def _mark_paid(session: Session, order: Order, pay: Payment, cap: PayPalCapture) -> None:
    pay.status, pay.verified_at, pay.failure_reason = "completed", _now(), ""
    _move(order, S.PAID)
    # Spending ledger in the user's currency, one row per product category, so spending analysis sees it.
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    merchants = set()
    for item in order.items:
        p = session.get(Product, item.product_id)
        by_category[p.category] += item.line_total
        merchants.add(p.merchant.name)
    if order.shipping > 0:
        by_category["Shipping"] += order.shipping
    for category, amount in by_category.items():
        session.add(Transaction(
            user_id=order.user_id, occurred_on=_now().date(), merchant=", ".join(sorted(merchants))[:120], category=category,
            amount=amount, currency=order.currency, source="paypal",
            fingerprint=hashlib.sha256(f"paypal:{cap.id}:{category}".encode()).hexdigest(),
        ))
    audit(session, order.user_id, "system", "payment_captured", order.id, {
        "payment_id": str(pay.id), "paypal_order_id": pay.provider_order_id, "capture_id": cap.id,
        "charged": fmt(pay.amount, pay.currency), "total": f"{order.total:.2f}",
    })
    _set_workflow(session, order, "paid", f"Paid. PayPal confirmed capture {cap.id} for {fmt(pay.amount, pay.currency)}.")
    # Only now, after verification, does the Post-Purchase agent record the purchase.
    from app.agents.post_purchase import record_purchase

    record_purchase(session, order, pay.verified_at)


# ---------- reconcile ----------


def reconcile(session: Session, order: Order, pay: Payment, paypal: PayPalClient) -> dict:
    """Ask PayPal what actually happened and record exactly that. Never guesses."""
    try:
        ppo, body = pp_orders.get_order(paypal, pay.provider_order_id)
    except PayPalAPIError as e:
        if e.status_code == 404:
            return _apply(session, order, pay, PayPalOrder(id=pay.provider_order_id, status="VOIDED"))
        return _still_unknown(session, order, pay, f"PayPal answered {e.status_code} when we checked.")
    except PayPalError:
        return _still_unknown(session, order, pay, "Couldn't reach PayPal to confirm. Nothing is assumed; check again.")
    _record_paypal(session, pay, "RECONCILE", body)
    return _apply(session, order, pay, ppo)


def _still_unknown(session: Session, order: Order, pay: Payment, reason: str) -> dict:
    _move(order, S.RECONCILIATION_REQUIRED)
    pay.status, pay.failure_reason = "unknown", reason
    session.commit()
    return payment_view(session, order)


def reconcile_for_user(session: Session, user: User, payment_id: uuid.UUID, paypal: PayPalClient) -> dict:
    pay = session.get(Payment, payment_id)
    if pay is None:
        raise PaymentError("not_found", "Payment not found.", 404)
    order = _own_order(session, user, pay.order_id)
    if order.status == S.PAID or not pay.provider_order_id:
        return payment_view(session, order)
    if order.status == S.CAPTURING:
        if _aware(pay.updated_at) + STUCK_CAPTURE > _now():
            raise PaymentError("capture_in_progress", "A capture is still running. Check again in a minute.", 409)
        transition(order, S.RECONCILIATION_REQUIRED)
        session.commit()
    if order.status not in (S.RECONCILIATION_REQUIRED, S.AWAITING_BUYER_CHECKOUT):
        raise PaymentError("nothing_to_check", f"This order is {order.status.replace('_', ' ')}.", 409)
    return reconcile(session, order, pay, paypal)


# ---------- buyer cancel / user cancel ----------


def checkout_cancelled(session: Session, user: User, order_id: uuid.UUID, paypal_order_id: str) -> dict:
    """The buyer closed the PayPal window. Nothing was charged; the order stays ready to pay."""
    order = _own_order(session, user, order_id)
    pay = session.scalar(select(Payment).where(Payment.order_id == order.id, Payment.provider_order_id == paypal_order_id))
    if pay is None:
        raise PaymentError("unknown_paypal_order", "That PayPal order doesn't belong to this order.", 404)
    audit(session, user.id, "user", "checkout_cancelled", order.id, {"payment_id": str(pay.id), "paypal_order_id": paypal_order_id})
    session.commit()
    return payment_view(session, order)


def cancel_order(session: Session, user: User, order_id: uuid.UUID) -> dict:
    """The user calls off an approved, unpaid order. Its PayPal order is never captured."""
    order = _own_order(session, user, order_id)
    if order.status not in (S.APPROVED, S.AWAITING_BUYER_CHECKOUT):
        raise PaymentError("not_cancellable", f"This order can't be cancelled (it is {order.status.replace('_', ' ')}).", 409)
    transition(order, S.CANCELLED)
    for pay in _payments(session, order):
        if pay.status in ("creating", "created"):
            pay.status = "cancelled"
    audit(session, user.id, "user", "order_cancelled", order.id, {})
    _set_workflow(session, order, "cancelled", "You cancelled this order before paying. Nothing was charged.")
    session.commit()
    return payment_view(session, order)


# ---------- webhooks ----------


def handle_webhook(session: Session, paypal: PayPalClient, raw: bytes, headers: dict[str, str]) -> dict:
    webhook_id = get_settings().paypal_webhook_id
    if not webhook_id:
        raise PaymentError("webhook_not_configured", "PAYPAL_WEBHOOK_ID isn't set, so webhooks can't be verified.", 503)
    fields = signature_fields(headers)
    if fields is None:
        raise PaymentError("signature_missing", "PayPal signature headers are missing.", 400)
    try:
        event = WebhookEvent.model_validate_json(raw)
    except ValueError:
        raise PaymentError("bad_event", "Not a PayPal webhook event.", 400)
    try:
        verified = verify_signature(paypal, fields, webhook_id, raw)
    except PayPalError as e:
        raise _paypal_failure(e)  # 5xx, so PayPal retries later
    if not verified:
        raise PaymentError("signature_invalid", "Webhook signature didn't verify. Ignored.", 400)

    if session.scalar(select(PaymentEvent.id).where(PaymentEvent.provider_event_id == event.id)):
        return {"status": "duplicate", "event_id": event.id}
    paypal_order_id = event.paypal_order_id()
    pay = session.scalar(select(Payment).where(Payment.provider_order_id == paypal_order_id)) if paypal_order_id else None
    session.add(PaymentEvent(payment_id=pay.id if pay else None, provider_event_id=event.id, event_type=event.event_type,
                             payload=strip_personal_data(json.loads(raw))))
    try:
        session.commit()
    except IntegrityError:  # the same event arriving twice at once
        session.rollback()
        return {"status": "duplicate", "event_id": event.id}

    if event.event_type not in HANDLED_EVENTS or pay is None:
        return {"status": "ignored", "event_id": event.id}
    order = session.get(Order, pay.order_id)
    try:
        if event.event_type == "CHECKOUT.ORDER.APPROVED":
            audit(session, order.user_id, "paypal", "buyer_approved", order.id, {"payment_id": str(pay.id)})
            session.commit()
        elif order.status in (S.PAID, S.CAPTURING):
            pass  # already final, or our own capture call is about to report
        elif event.event_type == "CHECKOUT.PAYMENT-APPROVAL.REVERSED":
            _move(order, S.FAILED)
            pay.status, pay.failure_reason = "failed", "PayPal reversed the buyer's approval."
            audit(session, order.user_id, "paypal", "payment_failed", order.id, {"payment_id": str(pay.id), "reason": pay.failure_reason})
            _set_workflow(session, order, "failed", "PayPal reversed the payment approval. Nothing was charged.")
            session.commit()
        else:  # PAYMENT.CAPTURE.*: don't trust the payload's amounts, ask PayPal directly
            reconcile(session, order, pay, paypal)
    except InvalidTransition as e:
        session.rollback()
        audit(session, order.user_id, "paypal", "event_ignored", order.id, {"event_id": event.id, "type": event.event_type, "why": str(e)})
        session.commit()
    return {"status": "processed", "event_id": event.id}


# ---------- views ----------


def payment_view(session: Session, order: Order, pay: Payment | None = None) -> dict:
    pay = pay or _latest_payment(session, order)
    base = {"order_status": order.status}
    if pay is None:  # same shape, all empty
        return {**base, "id": None, "status": None, "attempt": None, "amount": None, "currency": None, "paypal_order_id": None,
                "paypal_status": None, "capture_id": None, "capture_status": None, "verified": False, "verified_at": None, "message": ""}
    return {
        **base,
        "id": str(pay.id), "status": pay.status, "attempt": pay.attempt,
        "amount": f"{pay.amount:.2f}", "currency": pay.currency,
        "paypal_order_id": pay.provider_order_id, "paypal_status": pay.paypal_status,
        "capture_id": pay.provider_capture_id, "capture_status": pay.capture_status,
        "verified": pay.verified_at is not None and order.status == S.PAID,
        "verified_at": _aware(pay.verified_at).isoformat() if pay.verified_at else None,
        "message": pay.failure_reason,
    }


def payment_for_user(session: Session, user: User, payment_id: uuid.UUID) -> dict:
    pay = session.get(Payment, payment_id)
    if pay is None:
        raise PaymentError("not_found", "Payment not found.", 404)
    return payment_view(session, _own_order(session, user, pay.order_id), pay)
