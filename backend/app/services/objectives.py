"""Objectives and their task plans.

Automatic tasks are ticked from real events only (agent runs finished, the approval, PayPal's
verified capture, every item rated). Manual tasks are ticked by the user. Nothing is marked done
because time passed or because an LLM said so.
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Approval, Feedback, Objective, Order, Task, User, Workflow

PAID = {"paid"}
APPROVED_OR_LATER = {"approved", "paypal_order_created", "awaiting_buyer_checkout", "capturing", "reconciliation_required", "paid"}
AGENT_STEPS = {"needs": "life_operations", "research": "consumer_buyer", "cart": "procurement", "budget": "financial"}


class ObjectiveError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _workflow(session: Session, objective: Objective) -> Workflow | None:
    return session.scalar(select(Workflow).where(Workflow.objective_id == objective.id))


def _order(session: Session, objective: Objective) -> Order | None:
    return session.scalar(select(Order).where(Order.objective_id == objective.id).order_by(Order.created_at.desc()).limit(1))


def save_plan(session: Session, objective: Objective, tasks: list[dict]) -> None:
    """Create the objective's tasks once. Re-running never duplicates or overwrites progress."""
    existing = {t.key for t in session.scalars(select(Task).where(Task.objective_id == objective.id))}
    for i, t in enumerate(tasks):
        if t["key"] in existing:
            continue
        session.add(Task(
            objective_id=objective.id, user_id=objective.user_id, key=t["key"], title=t["title"], detail=t.get("detail", ""),
            owner=t["owner"], tracking=t["tracking"], external=t.get("external", False), depends_on=t.get("depends_on", []),
            due_on=date.fromisoformat(t["due_on"]) if t.get("due_on") else None, position=i,
        ))


def ensure_plan(session: Session, objective: Objective) -> None:
    """Objectives from before task plans existed get one from their stored Life Operations result."""
    if session.scalar(select(func.count()).select_from(Task).where(Task.objective_id == objective.id)):
        return
    wf = _workflow(session, objective)
    life = ((wf.state.get("runs") or {}).get("life_operations") or {}) if wf else {}
    if life.get("status") != "completed":
        return
    from app.agents.life_operations import task_plan

    tasks = life.get("result", {}).get("tasks") or []
    if not tasks or "key" not in tasks[0]:  # old format: rebuild from the template and target date
        tasks, _ = task_plan(life.get("result", {}).get("template"), objective.deadline, objective.created_at.date() if objective.created_at else date.today())
    save_plan(session, objective, tasks)
    session.flush()


def refresh(session: Session, objective: Objective) -> None:
    """Tick automatic tasks from what actually happened."""
    wf = _workflow(session, objective)
    runs = (wf.state.get("runs") or {}) if wf else {}
    order = _order(session, objective)
    status = order.status if order else None
    facts = {key: (runs.get(agent) or {}).get("status") == "completed" for key, agent in AGENT_STEPS.items()}
    facts["approve"] = status in APPROVED_OR_LATER
    facts["pay"] = status in PAID
    if order is not None and status in PAID:
        rated = set(session.scalars(select(Feedback.product_id).where(Feedback.order_id == order.id)))
        facts["feedback"] = all(i.product_id in rated for i in order.items)

    now = datetime.now(timezone.utc)
    for t in session.scalars(select(Task).where(Task.objective_id == objective.id)):
        if t.tracking != "auto" or t.key not in facts:
            continue
        done = facts[t.key]
        if done and t.status != "done":
            t.status, t.completed_at = "done", now
        elif not done and t.status == "done":
            t.status, t.completed_at = "todo", None
        # Once paid, the returns task can carry the real earliest return-by date.
    if order is not None and status in PAID:
        returns = session.scalar(select(Task).where(Task.objective_id == objective.id, Task.key == "returns"))
        if returns and returns.due_on is None:
            from app.agents.post_purchase import follow_ups
            from app.services.payment import payment_view

            verified = payment_view(session, order).get("verified_at")
            if verified:
                items = follow_ups(session, order, date.fromisoformat(verified[:10]))
                if items:
                    returns.due_on = min(date.fromisoformat(i["return_by"]) for i in items)


def view(session: Session, objective: Objective, today: date | None = None) -> dict:
    today = today or date.today()
    ensure_plan(session, objective)
    refresh(session, objective)
    session.commit()
    tasks = list(session.scalars(select(Task).where(Task.objective_id == objective.id).order_by(Task.position)))
    done = {t.key for t in tasks if t.status == "done"}
    keyed = {t.key: t for t in tasks}

    out = []
    for t in tasks:
        waiting_on = [keyed[k].title for k in t.depends_on if k in keyed and k not in done]
        state = "done" if t.status == "done" else "waiting" if waiting_on else "ready"
        out.append({
            "id": str(t.id), "key": t.key, "title": t.title, "detail": t.detail, "owner": t.owner, "tracking": t.tracking,
            "external": t.external, "depends_on": [keyed[k].title for k in t.depends_on if k in keyed], "waiting_on": waiting_on,
            "due_on": t.due_on.isoformat() if t.due_on else None, "state": state,
            "overdue": state != "done" and t.due_on is not None and t.due_on < today,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        })

    wf = _workflow(session, objective)
    life = ((wf.state.get("runs") or {}).get("life_operations") or {}).get("result", {}) if wf else {}
    order = _order(session, objective)
    approval = session.scalar(select(Approval).where(Approval.order_id == order.id).order_by(Approval.created_at.desc()).limit(1)) if order else None
    return {
        "id": str(objective.id), "title": objective.title, "description": objective.description, "status": objective.status,
        "deadline": objective.deadline.isoformat() if objective.deadline else None,
        "budget_limit": f"{objective.budget_limit:.2f}" if objective.budget_limit is not None else None, "currency": objective.currency,
        "created_at": objective.created_at.isoformat() if objective.created_at else None,
        "progress": {"done": len(done), "total": len(tasks), "pct": round(len(done) / len(tasks) * 100) if tasks else 0},
        # Up next: ready tasks, soonest due first (undated ones after, in plan order).
        "next": sorted((x for x in out if x["state"] == "ready"), key=lambda x: (x["due_on"] is None, x["due_on"] or ""))[:3],
        "tasks": out,
        "warnings": life.get("warnings", []),
        "links": {
            "workflow_id": str(wf.id) if wf else None, "order_id": str(order.id) if order else None,
            "order_status": order.status if order else None, "approval_id": str(approval.id) if approval else None,
        },
    }


def summaries(session: Session, user: User, today: date | None = None) -> list[dict]:
    out = []
    for o in session.scalars(select(Objective).where(Objective.user_id == user.id).order_by(Objective.created_at.desc()).limit(20)):
        v = view(session, o, today)
        out.append({k: v[k] for k in ("id", "title", "status", "deadline", "progress", "created_at")}
                   | {"next": v["next"][0]["title"] if v["next"] else None, "overdue": sum(1 for t in v["tasks"] if t["overdue"])})
    return out


def own(session: Session, user: User, objective_id) -> Objective:
    o = session.get(Objective, objective_id)
    if o is None or o.user_id != user.id:
        raise ObjectiveError(404, "Objective not found.")
    return o


def set_done(session: Session, user: User, objective: Objective, task_id, done: bool) -> dict:
    t = session.get(Task, task_id)
    if t is None or t.objective_id != objective.id:
        raise ObjectiveError(404, "Task not found.")
    if t.tracking != "manual":
        raise ObjectiveError(409, "PersonalIQ ticks this one from real events (approval, PayPal, ratings), so it can't be set by hand.")
    if done:
        refresh(session, objective)
        deps = {x.key: x for x in session.scalars(select(Task).where(Task.objective_id == objective.id, Task.key.in_(t.depends_on or [])))}
        waiting = [d.title for d in deps.values() if d.status != "done"]
        if waiting:
            raise ObjectiveError(409, f"This waits on: {', '.join(waiting)}.")
    t.status, t.completed_at = ("done", datetime.now(timezone.utc)) if done else ("todo", None)
    session.commit()
    return view(session, objective)
