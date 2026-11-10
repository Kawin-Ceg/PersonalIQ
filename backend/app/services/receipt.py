"""The Decision Receipt: why this order exists, who decided what, and what PayPal confirmed.

Built only from stored records (the workflow's agent snapshots, the approval, the audit log, the
payment). Nothing is re-ranked or recomputed after the fact, so the receipt shows the decision as
it was made. "paid" appears only when the payment was verified against PayPal's capture.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.post_purchase import DELIVERY_NOTE, follow_ups
from app.models import AgentRun, Approval, Feedback, Order, Product, User, Workflow
from app.services.approval import AGENT_TITLES, _aware, _workflow
from app.services.payment import payment_view
from app.services.settlement import charge_for

TITLES = {**AGENT_TITLES, "post_purchase": "Post-Purchase recorded the purchase"}
AGENT_NAMES = {
    "supervisor_plan": "Supervisor", "supervisor_verify": "Supervisor", "life_operations": "Life Operations",
    "consumer_buyer": "Consumer Buyer", "procurement": "Procurement", "financial": "Financial Autopilot", "post_purchase": "Post-Purchase", "supervisor_recover": "Supervisor",
}

# Order status -> what the receipt may claim.
STATE = {
    "draft": "proposed", "awaiting_approval": "proposed",
    "approved": "approved",
    "paypal_order_created": "payment_pending", "awaiting_buyer_checkout": "payment_pending",
    "capturing": "payment_pending", "reconciliation_required": "payment_pending",
    "paid": "paid",
    "failed": "payment_failed",
    "rejected": "not_bought", "cancelled": "not_bought", "expired": "not_bought",
}


class ReceiptError(Exception):
    pass


def receipt_state(order: Order, payment: dict) -> str:
    state = STATE.get(order.status, "proposed")
    if state == "paid" and not payment.get("verified"):
        return "payment_pending"  # belt and braces: never "paid" without verification
    return state


def _runs(state: dict) -> dict:
    return state.get("runs") or {}


def _approved(session: Session, order: Order) -> Approval | None:
    return session.scalar(
        select(Approval).where(Approval.order_id == order.id, Approval.status == "approved").order_by(Approval.decided_at.desc()).limit(1)
    )


def _items(session: Session, order: Order, runs: dict, approval: Approval | None) -> list[dict]:
    candidates = (runs.get("consumer_buyer") or {}).get("result", {}).get("candidates", {})
    risk = (approval.details.get("risk", {}).get("items", {}) if approval else {})
    confirmed = approval.details.get("confirmed", {}) if approval else {}
    out = []
    for it in order.items:
        p = session.get(Product, it.product_id)
        need = (p.attributes or {}).get("need", "general")
        options = candidates.get(need, [])
        mine = next((c for c in options if c["product_id"] == str(p.id)), None)
        alternatives = []
        for c in options:
            if c["product_id"] == str(p.id):
                continue
            if mine and c["score"] > mine["score"]:
                why = f"Scored higher ({c['score']:.1f} vs {mine['score']:.1f}), but didn't fit the budget or you chose otherwise."
            elif mine:
                why = f"Lower match for you ({c['score']:.1f} vs {mine['score']:.1f})."
            else:
                why = f"Match score {c['score']:.1f}."
            alternatives.append({"name": c["name"], "score": c["score"], "rank": c["rank"], "why_not": why})
        r = risk.get(str(it.id), {})
        out.append({
            "id": str(it.id), "product_id": str(p.id), "name": p.name, "category": p.category, "need": need,
            "merchant": p.merchant.name, "quantity": it.quantity,
            "unit_price": f"{it.unit_price:.2f}", "line_total": f"{it.line_total:.2f}",
            "reason": it.reason, "score": mine["score"] if mine else r.get("match_score"), "rank": mine["rank"] if mine else r.get("rank"),
            "risk_level": r.get("level"), "risk_score": r.get("score"), "your_decision": confirmed.get(str(it.id)),
            "alternatives": alternatives[:3],
        })
    return out


def build(session: Session, user: User, order: Order) -> dict:
    if order.user_id != user.id:
        raise ReceiptError("not found")
    wf: Workflow | None = _workflow(session, order)
    state = wf.state if wf else {}
    runs = _runs(state)
    approval = _approved(session, order)
    pay = payment_view(session, order)
    rstate = receipt_state(order, pay)

    agents = []
    if wf:
        for r in session.scalars(select(AgentRun).where(AgentRun.workflow_id == wf.id).order_by(AgentRun.started_at)):
            agents.append({
                "agent": r.agent_name, "name": AGENT_NAMES.get(r.agent_name, r.agent_name), "title": TITLES.get(r.agent_name, r.agent_name),
                "status": r.status, "explanation": r.explanation,
                "duration_ms": int((_aware(r.finished_at) - _aware(r.started_at)).total_seconds() * 1000) if r.finished_at else None,
            })

    buyer = (runs.get("consumer_buyer") or {}).get("result", {})
    cart = (runs.get("procurement") or {}).get("result", {}).get("cart", {})
    fin = (runs.get("financial") or {}).get("result", {})
    budget = (approval.details.get("budget") if approval else None) or {}

    verified_on = date.fromisoformat(pay["verified_at"][:10]) if rstate == "paid" and pay.get("verified_at") else None
    intent = state.get("intent") or {}
    return {
        "order_id": str(order.id), "state": rstate, "order_status": order.status, "version": order.version,
        "request": {
            "message": intent.get("message", ""), "objective": intent.get("objective", ""),
            "understood_by": intent.get("understood_by"), "at": _aware(wf.created_at).isoformat() if wf else None,
        },
        "agents": agents,
        "research": {
            "ranked_needs": len(buyer.get("candidates", {})),
            "candidates_considered": sum(len(v) for v in buyer.get("candidates", {}).values()),
            "excluded": buyer.get("excluded", []),
            "weights": buyer.get("weights", {}),
            "skipped_needs": cart.get("skipped", []),
        },
        "items": _items(session, order, runs, approval),
        "financial": {
            "explanation": budget.get("explanation") or (fin.get("evaluation") or {}).get("explanation", ""),
            "budget_name": budget.get("budget_name"), "limit": budget.get("limit"), "remaining_after": budget.get("remaining_after"),
            "used_pct": budget.get("used_pct"), "within_budget": budget.get("within_budget"),
        },
        "approval": {
            "approved": approval is not None,
            "approved_at": _aware(approval.decided_at).isoformat() if approval and approval.decided_at else None,
            "version": approval.order_version if approval else None,
            "fingerprint": approval.order_hash[:12] if approval else None,
        },
        "totals": {
            "currency": order.currency, "subtotal": f"{order.subtotal:.2f}", "shipping": f"{order.shipping:.2f}",
            "tax": f"{order.tax:.2f}", "total": f"{order.total:.2f}", "charge": charge_for(order).as_dict(),
        },
        "payment": pay,
        "completed_at": pay.get("verified_at") if rstate == "paid" else None,
        "follow_up": {
            "items": follow_ups(session, order, verified_on) if verified_on else [],
            "delivery_note": DELIVERY_NOTE,
        },
        "notes": [
            "Products, prices, ratings and warranties come from the seeded demo catalog, not live merchants.",
            "Amounts in another currency use fixed demo exchange rates.",
            "Payments run on the PayPal Sandbox. No real money moves.",
        ],
    }


def purchases(session: Session, user: User) -> list[dict]:
    """Orders past the proposal stage, newest first, with what the receipt may claim."""
    rows = session.scalars(
        select(Order).where(Order.user_id == user.id, Order.status.not_in(("draft", "awaiting_approval"))).order_by(Order.updated_at.desc())
    )
    out = []
    for o in rows:
        pay = payment_view(session, o)
        wf = _workflow(session, o)
        feedback_left = 0
        if o.status == "paid":
            # Items still waiting for feedback.
            rated = set(session.scalars(select(Feedback.product_id).where(Feedback.order_id == o.id)))
            feedback_left = sum(1 for i in o.items if i.product_id not in rated)
        out.append({
            "order_id": str(o.id), "state": receipt_state(o, pay), "order_status": o.status,
            "objective": wf.state.get("intent", {}).get("objective", "") if wf else "",
            "total": f"{o.total:.2f}", "currency": o.currency, "items": len(o.items),
            "charged": {"amount": pay.get("amount"), "currency": pay.get("currency")} if pay.get("verified") else None,
            "paid_at": pay.get("verified_at") if pay.get("verified") else None,
            "updated_at": _aware(o.updated_at).isoformat() if o.updated_at else None,
            "feedback_left": feedback_left,
        })
    return out

