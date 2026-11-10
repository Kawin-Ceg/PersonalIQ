"""The approval boundary. An approval authorises ONE exact order version.

- The order is fingerprinted (hash of items, prices, quantities, merchants, currency, totals).
- Any change (swap or remove an item) bumps the order version, supersedes the old approval and
  creates a new one, so an old "yes" can never pay for a different order.
- Approvals expire after 24 hours.
- Items the risk policy marks "needs_decision" must be kept, swapped or removed first.
- Every step is written to the audit log, which feeds the order timeline.
"""

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentRun, Approval, AuditLog, Feedback, Merchant, Objective, Order, OrderItem, Product, Transaction, User, Workflow
from app.schemas.catalog import product_out
from app.services.budget import evaluate, evaluate_saved_budget, recently_bought_needs
from app.services.catalog import search_products
from app.services.fx import convert, fmt
from app.services.personal_intelligence import build_user_context
from app.services.ranking import need_of, rank_products
from app.services.order_state import OrderStatus, transition
from app.services.risk import ItemFacts, UserFacts, assess_item, assess_order
from app.services.settlement import charge_for

APPROVAL_TTL = timedelta(hours=24)
CENT = Decimal("0.01")


class ApprovalError(Exception):
    """Refusal with a machine code (for the API status) and a plain message (for the user)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite drops tzinfo


def audit(session: Session, user_id, actor: str, action: str, order_id, detail: dict) -> None:
    session.add(AuditLog(user_id=user_id, actor=actor, action=action, entity="order", entity_id=str(order_id), detail=detail))


# ---------- the order fingerprint ----------


def order_hash(order: Order) -> str:
    charge = charge_for(order)
    items = sorted(
        (
            {"product_id": str(i.product_id), "quantity": i.quantity, "unit_price": f"{i.unit_price:.2f}", "line_total": f"{i.line_total:.2f}"}
            for i in order.items
        ),
        key=lambda x: x["product_id"],
    )
    payload = {
        "order_id": str(order.id), "version": order.version, "currency": order.currency,
        "subtotal": f"{order.subtotal:.2f}", "shipping": f"{order.shipping:.2f}", "tax": f"{order.tax:.2f}", "total": f"{order.total:.2f}",
        "items": items,
        # What PayPal will charge (currency + amount), so the approval covers that too.
        "charge": {"currency": charge.currency, "total": f"{charge.total:.2f}"},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# ---------- facts for the risk policy ----------


def _workflow(session: Session, order: Order) -> Workflow | None:
    return session.scalar(select(Workflow).where(Workflow.objective_id == order.objective_id)) if order.objective_id else None


def _plan(wf: Workflow | None) -> dict:
    return ((wf.state.get("runs") or {}).get("supervisor_plan") or {}).get("result") or {} if wf else {}


def _required(wf: Workflow | None) -> dict[str, bool]:
    life = ((wf.state.get("runs") or {}).get("life_operations") or {}).get("result") or {} if wf else {}
    return {n["need"]: n["required"] for n in life.get("needs", [])}


def _budget(session: Session, user: User, order: Order, wf: Workflow | None) -> dict:
    plan = _plan(wf)
    raw = evaluate_saved_budget(session, user.id, plan["budget_name"], order.total) if plan.get("budget_name") else None
    if raw is None and plan.get("budget"):
        raw = evaluate("request", Decimal(plan["budget"]), Decimal("0"), order.total, order.currency)
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in (raw or {}).items()}


def _user_facts(session: Session, user: User, budget: dict) -> UserFacts:
    ctx = build_user_context(session, user)
    ratings: dict[str, list[int]] = defaultdict(list)
    for category, rating in session.execute(
        select(Product.category, Feedback.rating).join(Feedback, Feedback.product_id == Product.id).where(Feedback.user_id == user.id)
    ):
        ratings[category].append(rating)
    known = set(session.scalars(select(Transaction.merchant).where(Transaction.user_id == user.id).distinct()))
    return UserFacts(
        currency=user.currency,
        budget_limit=Decimal(budget["limit"]) if budget.get("limit") else None,
        monthly_average=Decimal(ctx.spending.monthly_average) if ctx.spending else None,
        category_ratings={c: sum(r) / len(r) for c, r in ratings.items()},
        category_counts={c: len(r) for c, r in ratings.items()},
        liked_merchants=set(ctx.like_merchants),
        known_merchants=known,
    )


def _ranked_by_need(session: Session, user: User):
    return rank_products(session, search_products(session), build_user_context(session, user)).by_need()


def assess(session: Session, user: User, order: Order, wf: Workflow | None, budget: dict) -> dict:
    facts = _user_facts(session, user, budget)
    by_need = _ranked_by_need(session, user)
    required = _required(wf)
    dupes = recently_bought_needs(session, user.id)
    items = {}
    for it in order.items:
        p = session.get(Product, it.product_id)
        need = need_of(p)
        options = by_need.get(need, [])
        rank = next((s.rank for s in options if s.product.id == p.id), 99)
        score = next((s.score for s in options if s.product.id == p.id), 0.0)
        others = [s for s in options if s.product.id != p.id]
        top = options[0] if options else None
        f = ItemFacts(
            item_id=str(it.id), name=p.name, need=need, category=p.category, merchant_slug=p.merchant.slug, merchant_name=p.merchant.name,
            line_total=it.line_total, required=required.get(need, True), rank=rank, score=score,
            runner_up_name=others[0].product.name if others else None, runner_up_score=others[0].score if others else None,
            top_name=top.product.name if top and top.product.id != p.id else None, top_score=top.score if top else None,
            return_days=p.merchant.return_window_days, duplicate=need in dupes,
        )
        # "score" is the risk score (0-100); "match_score" is how well the product ranked for the user.
        items[str(it.id)] = {**assess_item(f, facts), "need": need, "rank": rank, "match_score": score, "required": f.required}
    return {"items": items, "order": assess_order(order.total, facts, items)}


# ---------- lifecycle ----------


def request_approval(session: Session, user: User, order: Order, wf: Workflow | None, confirmed: dict | None = None, actor: str = "agent:supervisor") -> Approval:
    session.flush()
    budget = _budget(session, user, order, wf)
    risk = assess(session, user, order, wf, budget)
    keep = {k: v for k, v in (confirmed or {}).items() if k in risk["items"]}
    approval = Approval(
        workflow_id=wf.id if wf else None, order_id=order.id, order_version=order.version, order_hash=order_hash(order),
        status="pending", expires_at=_now() + APPROVAL_TTL, details={"risk": risk, "confirmed": keep, "budget": budget, "charge": charge_for(order).as_dict()},
    )
    session.add(approval)
    session.flush()
    counts = risk["order"]["counts"]
    audit(session, user.id, actor, "approval_requested", order.id, {
        "approval_id": str(approval.id), "version": order.version, "total": f"{order.total:.2f}", "currency": order.currency,
        "needs_decision": counts["needs_decision"], "review": counts["review"], "auto": counts["auto"],
    })
    return approval


def expire_if_due(session: Session, approval: Approval) -> bool:
    if approval.status == "pending" and _aware(approval.expires_at) <= _now():
        approval.status = "expired"
        order = session.get(Order, approval.order_id)
        if order.status == OrderStatus.AWAITING_APPROVAL:
            transition(order, OrderStatus.EXPIRED)
        audit(session, order.user_id, "system", "approval_expired", order.id, {"approval_id": str(approval.id)})
        session.commit()
        return True
    return False


def pending_decisions(approval: Approval) -> list[str]:
    risk_items = approval.details.get("risk", {}).get("items", {})
    confirmed = approval.details.get("confirmed", {})
    return [iid for iid, r in risk_items.items() if r["level"] == "needs_decision" and iid not in confirmed]


def _check_open(session: Session, approval: Approval) -> Order:
    expire_if_due(session, approval)
    if approval.status == "expired":
        raise ApprovalError("expired", "This approval expired. Ask PersonalIQ to refresh the order.")
    if approval.status != "pending":
        raise ApprovalError("not_pending", f"This approval is already {approval.status}.")
    return session.get(Order, approval.order_id)


def _recompute(session: Session, order: Order) -> None:
    """Totals and shipping after a change, with the same merchant rules as the cart optimizer."""
    by_merchant: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for it in order.items:
        by_merchant[session.get(Product, it.product_id).merchant_id] += it.line_total
    shipping = Decimal("0")
    for merchant_id, subtotal in by_merchant.items():
        m = session.get(Merchant, merchant_id)
        free_over = convert(m.free_shipping_over, m.currency, order.currency) if m.free_shipping_over is not None else None
        if free_over is None or subtotal < free_over:
            shipping += convert(m.shipping_flat, m.currency, order.currency)
    order.subtotal = sum((i.line_total for i in order.items), Decimal("0")).quantize(CENT)
    order.shipping = shipping.quantize(CENT)
    order.total = (order.subtotal + order.shipping + order.tax).quantize(CENT)


def act_on_item(session: Session, user: User, approval: Approval, item_id: uuid.UUID, action: str, product_id: uuid.UUID | None = None) -> Approval:
    """keep: confirm as is. remove / swap: change the order, which replaces this approval."""
    order = _check_open(session, approval)
    item = next((i for i in order.items if i.id == item_id), None)
    if item is None:
        raise ApprovalError("not_found", "That item isn't in this order.")
    product = session.get(Product, item.product_id)

    if action == "keep":
        approval.details = {**approval.details, "confirmed": {**approval.details.get("confirmed", {}), str(item.id): "kept"}}
        audit(session, user.id, "user", "item_kept", order.id, {"item_id": str(item.id), "name": product.name})
        session.commit()
        return approval

    confirmed = dict(approval.details.get("confirmed", {}))
    if action == "remove":
        if len(order.items) == 1:
            raise ApprovalError("last_item", "This is the only item. Reject the order instead.")
        order.items.remove(item)
        confirmed.pop(str(item.id), None)
        audit(session, user.id, "user", "item_removed", order.id, {"item_id": str(item.id), "name": product.name, "amount": f"{item.line_total:.2f}"})
    elif action == "swap":
        new = session.get(Product, product_id) if product_id else None
        eligible = {s.product.id for s in _ranked_by_need(session, user).get(need_of(product), [])}
        if new is None or new.id not in eligible:
            raise ApprovalError("invalid_swap", "Pick one of the suggested alternatives for this item.")
        unit = convert(new.price, new.currency, order.currency)
        old_name, old_total = product.name, item.line_total
        item.product_id, item.unit_price = new.id, unit
        item.line_total = (unit * item.quantity).quantize(CENT)
        item.reason = f"You chose this instead of {old_name}."
        confirmed[str(item.id)] = "swapped"  # the user picked it, so it's decided
        audit(session, user.id, "user", "item_swapped", order.id, {
            "item_id": str(item.id), "from": old_name, "to": new.name, "from_amount": f"{old_total:.2f}", "to_amount": f"{item.line_total:.2f}",
        })
    else:
        raise ApprovalError("bad_action", "Unknown action.")

    session.flush()
    _recompute(session, order)
    order.version += 1
    approval.status = "superseded"
    transition(order, OrderStatus.AWAITING_APPROVAL)
    audit(session, user.id, "system", "order_changed", order.id, {"version": order.version, "total": f"{order.total:.2f}", "replaces": str(approval.id)})
    wf = _workflow(session, order)
    new_approval = request_approval(session, user, order, wf, confirmed, actor="system")
    if wf:
        outcome = wf.state.get("outcome") or {}
        wf.state = {**wf.state, "outcome": {**outcome, "result": {**(outcome.get("result") or {}), "approval_id": str(new_approval.id)}}}
    session.commit()
    return new_approval


def approve(session: Session, user: User, approval: Approval, seen_hash: str) -> Approval:
    order = _check_open(session, approval)
    if order.version != approval.order_version or order_hash(order) != approval.order_hash:
        raise ApprovalError("changed", "The order changed after this approval was created. Review the new version.")
    if seen_hash != approval.order_hash:
        raise ApprovalError("stale", "You were looking at an older version of this order. Review it again.")
    if pending := pending_decisions(approval):
        raise ApprovalError("decisions_needed", f"{len(pending)} item(s) still need your decision.")
    if approval.details.get("risk", {}).get("order", {}).get("over_budget"):
        raise ApprovalError("over_budget", "This order is over budget. Remove or swap an item first.")

    approval.status, approval.decided_at = "approved", _now()
    transition(order, OrderStatus.APPROVED)
    _set_workflow(session, order, "approved", "Approved. Next: pay with PayPal Sandbox.")
    audit(session, user.id, "user", "approved", order.id, {"approval_id": str(approval.id), "version": order.version, "total": f"{order.total:.2f}", "hash": approval.order_hash})
    session.commit()
    return approval


def reject(session: Session, user: User, approval: Approval, reason: str | None) -> Approval:
    order = _check_open(session, approval)
    approval.status, approval.decided_at = "rejected", _now()
    transition(order, OrderStatus.REJECTED)
    _set_workflow(session, order, "rejected", "You rejected this order. Nothing was bought.")
    audit(session, user.id, "user", "rejected", order.id, {"approval_id": str(approval.id), "reason": reason})
    if reason:
        # Feeds the Personal Intelligence Engine (e.g. two "too expensive" rejections raise price sensitivity).
        from app.services.personal_intelligence import record_event

        record_event(session, user, "recommendation_rejected", None, {"reason": reason, "order_id": str(order.id)})
    session.commit()
    return approval


def _set_workflow(session: Session, order: Order, status: str, message: str) -> None:
    wf = _workflow(session, order)
    if wf:
        wf.status = status
        outcome = wf.state.get("outcome") or {}
        wf.state = {**wf.state, "outcome": {**outcome, "status": status, "message": message}}
    if order.objective_id:
        session.get(Objective, order.objective_id).status = status


# ---------- views and timelines ----------


def alternatives(session: Session, by_need: dict, item: OrderItem, currency: str) -> list[dict]:
    p = session.get(Product, item.product_id)
    out = []
    for s in by_need.get(need_of(p), []):
        if s.product.id == p.id:
            continue
        new_total = (convert(s.product.price, s.product.currency, currency) * item.quantity).quantize(CENT)
        out.append({
            "product": product_out(s.product, currency).model_dump(mode="json"), "score": s.score, "rank": s.rank,
            "difference": f"{new_total - item.line_total:.2f}",  # change to the order total if swapped (before shipping)
        })
    return out[:3]


def _events(session: Session, order: Order) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.entity == "order", AuditLog.entity_id == str(order.id)).order_by(AuditLog.occurred_at)))


AGENT_TITLES = {
    "supervisor_plan": "Supervisor planned the work",
    "life_operations": "Life Operations listed what you need",
    "consumer_buyer": "Consumer Buyer ranked the products",
    "procurement": "Procurement built the cart",
    "financial": "Financial Autopilot checked the budget",
    "supervisor_recover": "Supervisor changed course",
    "supervisor_verify": "Supervisor verified the outcome",
}


def _event_text(e: AuditLog, cur: str) -> tuple[str, str, str]:
    d = e.detail
    money = lambda key: fmt(Decimal(d[key]), cur)  # noqa: E731
    return {
        "approval_requested": ("decision", "Approval requested", f"Version {d.get('version')}, {money('total') if 'total' in d else ''}. "
                               f"{d.get('needs_decision', 0)} need your decision, {d.get('review', 0)} worth a look, {d.get('auto', 0)} confident."),
        "item_kept": ("user", f"You kept {d.get('name')}", ""),
        "item_removed": ("user", f"You removed {d.get('name')}", money("amount") if "amount" in d else ""),
        "item_swapped": ("user", f"You swapped {d.get('from')} for {d.get('to')}",
                         f"{money('from_amount')} to {money('to_amount')}" if "from_amount" in d else ""),
        "order_changed": ("system", f"Order updated to version {d.get('version')}", f"New total {money('total')}. The earlier approval no longer applies." if "total" in d else ""),
        "approved": ("success", "You approved the order", f"{money('total')}, version {d.get('version')}" if "total" in d else ""),
        "rejected": ("danger", "You rejected the order", d.get("reason") or ""),
        "approval_expired": ("danger", "Approval expired", "Not approved within 24 hours."),
        "approval_invalidated": ("danger", "Approval no longer valid", f"{d.get('reason', '')} Version {d.get('version')} needs approving."),
        "payment_window_expired": ("danger", "Approval expired before payment", "Approved orders must be paid within 24 hours."),
        "paypal_order_created": ("system", "PayPal checkout created", f"{d.get('charged', '')} · PayPal order {d.get('paypal_order_id', '')}"),
        "paypal_order_failed": ("danger", "Couldn't create the PayPal checkout", d.get("reason", "")),
        "checkout_cancelled": ("user", "You closed PayPal checkout", "Nothing was charged."),
        "buyer_approved": ("system", "PayPal: buyer approved the payment", ""),
        "capture_started": ("system", "Capturing the payment", f"PayPal order {d.get('paypal_order_id', '')}"),
        "capture_uncertain": ("danger", "PayPal didn't answer in time", "Not assumed failed. Checking with PayPal."),
        "capture_declined": ("danger", "PayPal declined the payment method", "Pick another way to pay."),
        "payment_not_captured": ("system", "Checked with PayPal: not captured", f"PayPal status {d.get('paypal_status', '')}. Nothing was charged."),
        "paypal_order_voided": ("system", "PayPal voided the checkout", "Nothing was charged."),
        "payment_pending": ("decision", "PayPal is holding the payment", d.get("reason", "")),
        "payment_mismatch": ("danger", "Capture doesn't match the approved order", "; ".join(d.get("problems", []))),
        "payment_failed": ("danger", "Payment failed", d.get("reason", "")),
        "payment_captured": ("success", "Paid, verified with PayPal", f"{d.get('charged', '')} · capture {d.get('capture_id', '')}"),
        "order_cancelled": ("danger", "You cancelled the order", "Nothing was charged."),
        "event_ignored": ("system", "PayPal event ignored", d.get("why", "")),
    }.get(e.action, ("system", e.action.replace("_", " ").capitalize(), ""))


def order_timeline(session: Session, order: Order) -> list[dict]:
    out = []
    wf = _workflow(session, order)
    if wf:
        out.append({"at": _aware(wf.created_at).isoformat(), "kind": "start", "title": "You asked PersonalIQ", "detail": wf.state["intent"]["message"], "actor": "user"})
        for r in session.scalars(select(AgentRun).where(AgentRun.workflow_id == wf.id).order_by(AgentRun.started_at)):
            if r.finished_at:
                out.append({"at": _aware(r.finished_at).isoformat(), "kind": "agent", "title": AGENT_TITLES.get(r.agent_name, r.agent_name), "detail": r.explanation, "actor": r.agent_name})
    for e in _events(session, order):
        kind, title, detail = _event_text(e, order.currency)
        out.append({"at": _aware(e.occurred_at).isoformat(), "kind": kind, "title": title, "detail": detail, "actor": e.actor})
    return out


def item_trail(session: Session, approval: Approval, order: Order, item: OrderItem) -> list[dict]:
    """Every decision about one item, in order: ranked, picked, budget, risk, what you did."""
    risk = approval.details["risk"]["items"].get(str(item.id), {})
    p = session.get(Product, item.product_id)
    budget = approval.details.get("budget") or {}
    trail = [
        {"step": "Ranked", "actor": "Consumer Buyer", "detail": f"#{risk.get('rank', '?')} of the options for {need_of(p).replace('_', ' ')}, match score {risk.get('match_score', 0):.1f}."},
        {"step": "Picked", "actor": "Procurement", "detail": item.reason or "Best fit within the budget."},
    ]
    if budget.get("explanation"):
        trail.append({"step": "Budget checked", "actor": "Financial Autopilot", "detail": budget["explanation"]})
    trail.append({
        "step": "Risk assessed", "actor": "Risk policy",
        "detail": {"needs_decision": "Needs your decision", "review": "Worth a look", "auto": "PersonalIQ is confident"}.get(risk.get("level"), "")
        + f" (risk {risk.get('score', 0)}/100).",
        "factors": risk.get("factors", []),
    })
    for e in _events(session, order):
        if e.detail.get("item_id") == str(item.id):
            _, title, detail = _event_text(e, order.currency)
            trail.append({"step": title, "actor": "You", "detail": detail, "at": _aware(e.occurred_at).isoformat()})
    return trail


def view(session: Session, user: User, approval: Approval) -> dict:
    expire_if_due(session, approval)
    order = session.get(Order, approval.order_id)
    wf = _workflow(session, order)
    risk = approval.details.get("risk", {})
    confirmed = approval.details.get("confirmed", {})
    by_need = _ranked_by_need(session, user) if approval.status == "pending" else {}  # rank once, not per item
    items = []
    for it in order.items:
        r = risk.get("items", {}).get(str(it.id), {"level": "auto", "score": 0, "factors": []})
        items.append({
            "id": str(it.id),
            "product": product_out(session.get(Product, it.product_id), order.currency).model_dump(mode="json"),
            "quantity": it.quantity, "unit_price": f"{it.unit_price:.2f}", "line_total": f"{it.line_total:.2f}", "reason": it.reason,
            "risk": r, "decision": confirmed.get(str(it.id)),
            "trail": item_trail(session, approval, order, it),
            "alternatives": alternatives(session, by_need, it, order.currency),
        })
    order_info = risk.get("order", {})
    blockers = []
    if approval.status != "pending":
        blockers.append(f"This approval is {approval.status}.")
    if pending := pending_decisions(approval):
        blockers.append(f"{len(pending)} item(s) need your decision.")
    if order_info.get("over_budget"):
        over = next((f["reason"] for f in order_info.get("factors", []) if f["factor"] == "over_budget"), "")
        blockers.append(f"The order is {over.rstrip('.')}. Remove an item or swap for a cheaper one.")
    newer = session.scalar(
        select(Approval.id).where(Approval.order_id == order.id, Approval.status == "pending", Approval.id != approval.id)
    )
    return {
        "id": str(approval.id), "status": approval.status, "order_hash": approval.order_hash, "order_version": approval.order_version,
        "expires_at": _aware(approval.expires_at).isoformat(), "created_at": _aware(approval.created_at).isoformat() if approval.created_at else None,
        "objective": wf.state["intent"]["objective"] if wf else "", "workflow_id": str(wf.id) if wf else None,
        "order": {
            "id": str(order.id), "status": order.status, "version": order.version, "currency": order.currency,
            "subtotal": f"{order.subtotal:.2f}", "shipping": f"{order.shipping:.2f}", "tax": f"{order.tax:.2f}", "total": f"{order.total:.2f}",
            "merchants": sorted({i["product"]["merchant"]["name"] for i in items}),
        },
        "items": sorted(items, key=lambda i: -i["risk"]["score"]),
        "risk": order_info, "budget": approval.details.get("budget", {}),
        "can_approve": not blockers, "blockers": blockers,
        "replaced_by": str(newer) if newer and approval.status in ("superseded", "invalidated") else None,
        "timeline": order_timeline(session, order),
        "payment_method": "PayPal Sandbox",
        "charge": approval.details.get("charge") or charge_for(order).as_dict(),
        "payment": _payment_view(session, order),
    }


def _payment_view(session: Session, order: Order) -> dict | None:
    from app.services.payment import payment_view  # payment builds on approval, so import late

    return payment_view(session, order)


def pending_for(session: Session, user: User) -> list[Approval]:
    rows = list(
        session.scalars(
            select(Approval).join(Order, Order.id == Approval.order_id).where(Order.user_id == user.id, Approval.status == "pending").order_by(Approval.created_at.desc())
        )
    )
    return [a for a in rows if not expire_if_due(session, a)]


def count_pending(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).select_from(Approval).join(Order, Order.id == Approval.order_id).where(Order.user_id == user.id, Approval.status == "pending")
    ) or 0
