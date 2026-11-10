"""Financial Autopilot agent: checks the proposed cart against budgets and recent purchases.

All arithmetic is in services/budget.py. This agent decides which check applies and reports flags.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.agents import AgentResult, AgentTask
from app.schemas.personal import UserContext
from app.services.budget import DUPLICATE_WINDOW_DAYS, evaluate, evaluate_saved_budget, recently_bought_needs


def run(task: AgentTask, session: Session, ctx: UserContext) -> AgentResult:
    cart = task.context.get("cart")
    if not cart or not cart.get("feasible"):
        return AgentResult(task_id=task.task_id, status="skipped", explanation="No cart to check.")

    total = Decimal(cart["total"])
    name = task.constraints.get("budget_name")
    ev = evaluate_saved_budget(session, ctx.user_id, name, total) if name else None
    if ev is None:
        ev = evaluate("request", Decimal(task.constraints["budget"]), Decimal("0"), total, ctx.currency)

    flags = []
    if not ev["within_budget"]:
        flags.append({"level": "block", "message": ev["explanation"]})
    duplicates = sorted({line["need"] for line in cart["lines"]} & recently_bought_needs(session, ctx.user_id))
    for need in duplicates:
        flags.append({"level": "warn", "message": f"You bought a {need.replace('_', ' ')} in the last {DUPLICATE_WINDOW_DAYS} days."})
    if ev["used_pct"] >= 90 and ev["within_budget"]:
        flags.append({"level": "info", "message": f"This uses {ev['used_pct']}% of the budget."})

    ok = not any(f["level"] == "block" for f in flags)
    return AgentResult(
        task_id=task.task_id,
        status="completed" if ok else "failed",
        result={"evaluation": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in ev.items()}, "flags": flags, "approved_by_policy": ok},
        explanation=ev["explanation"],
        requires_human_approval=ok,
        errors=[] if ok else [ev["explanation"]],
    )
