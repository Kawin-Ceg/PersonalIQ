"""Post-Purchase agent: runs once, right after PayPal confirms a capture.

It records the purchase and its follow-ups: return deadlines (from each merchant's return window),
warranty end dates (from the demo catalog), and a feedback request per item. It never invents a
delivery, warranty claim or refund status: the demo catalog has no delivery tracking, so it says so.
Deterministic, no LLM.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentRun, Feedback, Order, Product, Workflow
from app.schemas.agents import AgentResult, AgentTask

WAITING_EXPLANATION = "Waiting for your approval and a verified payment before recording the purchase."
FEEDBACK_AFTER_DAYS = 14  # when we ask "how is it going?" for items that need some use first
DELIVERY_NOTE = "Delivery tracking isn't available for the demo catalog."


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):  # clamp, e.g. 31 Jan + 1 month -> 28/29 Feb
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError("bad date")  # pragma: no cover


def follow_ups(session: Session, order: Order, paid_on: date) -> list[dict]:
    """One entry per item: when it can be returned until, warranty end, and whether feedback was given."""
    given = {
        f.product_id: f
        for f in session.scalars(select(Feedback).where(Feedback.order_id == order.id))
    }
    out = []
    for item in order.items:
        p = session.get(Product, item.product_id)
        fb = given.get(p.id)
        out.append({
            "item_id": str(item.id), "product_id": str(p.id), "name": p.name, "category": p.category,
            "merchant": p.merchant.name,
            "return_by": (paid_on + timedelta(days=p.merchant.return_window_days)).isoformat(),
            "return_window_days": p.merchant.return_window_days,
            "warranty_until": _add_months(paid_on, p.warranty_months).isoformat() if p.warranty_months else None,
            "warranty_months": p.warranty_months,
            "feedback_after": (paid_on + timedelta(days=FEEDBACK_AFTER_DAYS)).isoformat(),
            "feedback": {"rating": fb.rating, "aspects": fb.aspects or {}, "worked": fb.worked, "didnt_work": fb.didnt_work, "at": fb.created_at.isoformat() if fb.created_at else None} if fb else None,
            "delivery": None,  # unknown: never guessed
        })
    return out


def run(task: AgentTask, session: Session, order: Order, paid_at: datetime) -> AgentResult:
    items = follow_ups(session, order, paid_at.date())
    merchants = sorted({i["merchant"] for i in items})
    first_return = min(items, key=lambda i: i["return_by"])
    return AgentResult(
        task_id=task.task_id,
        status="completed",
        result={"order_id": str(order.id), "follow_ups": items, "delivery_note": DELIVERY_NOTE, "feedback_after_days": FEEDBACK_AFTER_DAYS},
        explanation=(
            f"Recorded {len(items)} items from {len(merchants)} store{'s' if len(merchants) != 1 else ''}. "
            f"First return window closes {date.fromisoformat(first_return['return_by']).strftime('%d %b %Y')} ({first_return['merchant']}). "
            f"I'll ask how each item works out, so future picks learn from it."
        ),
    )


def record_purchase(session: Session, order: Order, paid_at: datetime) -> AgentRun | None:
    """Called by the payment service after a VERIFIED capture. Runs once per workflow; no-op without one."""
    wf = session.scalar(select(Workflow).where(Workflow.objective_id == order.objective_id)) if order.objective_id else None
    if wf is None:
        return None
    existing = session.scalar(select(AgentRun).where(AgentRun.workflow_id == wf.id, AgentRun.agent_name == "post_purchase"))
    if existing:
        return existing
    started = datetime.now(timezone.utc)
    task = AgentTask(workflow_id=wf.id, user_id=order.user_id, agent_name="post_purchase", objective="Record the purchase after payment",
                     context={"order_id": str(order.id)})
    result = run(task, session, order, paid_at)
    agent_run = AgentRun(
        workflow_id=wf.id, agent_name="post_purchase", status=result.status, input={"order_id": str(order.id)},
        output=result.model_dump(mode="json"), explanation=result.explanation, started_at=started, finished_at=datetime.now(timezone.utc),
    )
    session.add(agent_run)
    runs = dict(wf.state.get("runs") or {})
    runs["post_purchase"] = {"status": result.status, "result": result.result, "explanation": result.explanation}
    wf.state = {**wf.state, "runs": runs}
    return agent_run
