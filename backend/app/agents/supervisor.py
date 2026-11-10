"""Central supervisor: plans the work, and verifies the outcome at the end.

Planning decides the budget (and where it came from) and which agents run in what order.
Verification turns the agents' results into exactly one outcome:
  awaiting_approval  a verified, in-budget cart was saved as a proposed order
  needs_input        PersonalIQ needs something from the user (a question is attached)
  blocked            the goal can't be met as asked (the reason is attached)
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import get_llm
from app.models import Budget, Order, OrderItem
from app.schemas.agents import AgentResult, AgentTask, Intent
from app.schemas.personal import UserContext
from app.services.budget import resolve_budget
from app.services.fx import fmt

PLAN = [
    {"agent": "life_operations", "goal": "Work out what you need", "depends_on": []},
    {"agent": "consumer_buyer", "goal": "Research and rank products for you", "depends_on": []},
    {"agent": "procurement", "goal": "Build the best cart within budget", "depends_on": ["life_operations", "consumer_buyer"]},
    {"agent": "financial", "goal": "Check the cart against your budgets", "depends_on": ["procurement"]},
    {"agent": "post_purchase", "goal": "Record the purchase after payment", "depends_on": ["approval", "payment"]},
]


def plan(task: AgentTask, session: Session, ctx: UserContext) -> AgentResult:
    intent = Intent.model_validate(task.context["intent"])
    budget, name, source = intent.budget, None, "your request"
    if budget is None:
        # No amount in the request: use the matching saved budget, else the monthly one.
        pick = resolve_budget(session, ctx.user_id, intent.template)
        if pick is None:
            return AgentResult(
                task_id=task.task_id,
                status="needs_input",
                result={"question": "How much would you like to spend?"},
                explanation="No budget in the request and no saved budget to use.",
            )
        budget, name, source = pick.limit_amount, pick.name, f"your {pick.name} budget"

    note = f" {intent.budget_note}" if intent.budget_note else ""
    return AgentResult(
        task_id=task.task_id,
        status="completed",
        result={"plan": PLAN, "budget": f"{budget:.2f}", "budget_name": name, "budget_source": source},
        explanation=f"Budget {fmt(budget, ctx.currency)} from {source}.{note} Life Operations and Buyer start in parallel.",
    )


# ---------- recovery: decided from the agents' results, bounded ----------

MAX_RECOVERIES = 2
DEEP_SEARCH_DEPTH = 12  # candidates per need when searching deeper (normal: 4)
STRATEGY_LABEL = {
    "fit_remaining": "rebuilding the cart for what's left of the budget",
    "deeper_search": "searching deeper for cheaper options",
}


def decide_recovery(runs: dict, recovery: dict, currency: str) -> dict | None:
    """What to try when the cart or the budget check failed. Each strategy at most once, two in total."""
    tried = recovery.get("tried", [])
    if len(tried) >= MAX_RECOVERIES:
        return None
    proc, fin = runs.get("procurement", {}), runs.get("financial", {})

    # The cart fit the planned amount, but earlier orders already used part of that saved budget.
    if proc.get("status") == "completed" and fin.get("status") == "failed" and "fit_remaining" not in tried:
        ev = fin.get("result", {}).get("evaluation", {})
        if ev.get("limit") and ev.get("committed") is not None:
            limit, committed = Decimal(ev["limit"]), Decimal(ev["committed"])
            remaining = limit - committed
            if committed > 0 and remaining > 0:
                return {
                    "strategy": "fit_remaining", "budget": f"{remaining:.2f}",
                    "reason": f"Earlier orders already used {fmt(committed, currency)} of your {ev.get('budget_name', '')} budget, "
                              f"so {fmt(remaining, currency)} is left. Asking Procurement to rebuild the cart to fit that.",
                }

    # The must-haves didn't fit: look further down each item's ranking for cheaper options.
    if proc.get("status") == "failed" and "deeper_search" not in tried:
        return {
            "strategy": "deeper_search", "depth": DEEP_SEARCH_DEPTH,
            "reason": f"The cart didn't fit: {proc.get('explanation', '')} Asking Consumer Buyer for up to {DEEP_SEARCH_DEPTH} options "
                      f"per item, cheaper ones included, then rebuilding the cart.",
        }
    return None


def policy_violations(cart: dict, budget: Decimal, candidates: dict, currency: str) -> list[str]:
    """Hard rules checked in code before any order is proposed."""
    out = []
    if Decimal(cart["total"]) > budget:
        out.append(f"total {fmt(Decimal(cart['total']), currency)} is over the {fmt(budget, currency)} budget")
    if cart.get("currency") != currency:
        out.append(f"cart is in {cart.get('currency')}, not {currency}")
    researched = {c["product_id"] for items in candidates.values() for c in items}
    for line in cart.get("lines", []):
        if line["product"]["id"] not in researched:
            out.append(f"{line['product']['name']} wasn't among the researched products")
        if int(line["quantity"]) < 1:
            out.append(f"{line['product']['name']} has an invalid quantity")
    if not cart.get("lines"):
        out.append("the cart is empty")
    return out


def verify(session: Session, ctx: UserContext, workflow_id: uuid.UUID, objective_id: uuid.UUID | None, state: dict) -> dict:
    """Decide the workflow outcome. Returns {status, message, result}."""
    runs = state.get("runs", {})

    # Life Operations' task plan becomes the objective's tracked tasks, whatever the outcome.
    life = runs.get("life_operations", {})
    if objective_id and life.get("status") == "completed" and life.get("result", {}).get("tasks"):
        from app.models import Objective
        from app.services.objectives import save_plan

        objective = session.get(Objective, objective_id)
        if objective is not None:
            save_plan(session, objective, life["result"]["tasks"])

    for agent in ("supervisor_plan", "life_operations"):
        r = runs.get(agent, {})
        if r.get("status") == "needs_input":
            return {"status": "needs_input", "message": r["result"]["question"], "result": {"question": r["result"]["question"]}}

    tried = (state.get("recovery") or {}).get("tried", [])
    tried_note = f" I also tried: {'; '.join(STRATEGY_LABEL[t] for t in tried)}." if tried else ""
    failed = [a for a, r in runs.items() if r.get("status") == "failed"]
    if failed:
        reason = runs[failed[0]].get("errors", ["Something went wrong."])[0]
        return {"status": "blocked", "message": f"I can't complete this as asked. {reason}{tried_note}",
                "result": {"reason": reason, "agent": failed[0], "recovery_tried": tried}}
    if any(runs.get(k, {}).get("status") != "completed" for k in ("procurement", "financial")):
        reason = "The workflow stopped before a cart was built and checked (time or step limit)."
        return {"status": "blocked", "message": f"I can't complete this right now. {reason}", "result": {"reason": reason, "agent": "supervisor"}}

    cart = runs["procurement"]["result"]["cart"]
    fin = runs["financial"]["result"]

    # Policy gate: nothing becomes an order unless code confirms these, whatever any agent said.
    plan_budget = Decimal((state.get("recovery") or {}).get("budget") or runs["supervisor_plan"]["result"]["budget"])
    candidates = runs.get("consumer_buyer", {}).get("result", {}).get("candidates", {})
    violations = policy_violations(cart, plan_budget, candidates, ctx.currency)
    if violations:
        reason = "Policy check failed: " + "; ".join(violations) + "."
        return {"status": "blocked", "message": f"I won't propose this order. {reason}", "result": {"reason": reason, "agent": "supervisor"}}

    # Attribute the order to the saved budget it was planned against (else the matching / monthly one).
    plan = runs.get("supervisor_plan", {}).get("result", {})
    budget_row = (
        session.scalar(select(Budget).where(Budget.user_id == ctx.user_id, Budget.name == plan["budget_name"]))
        if plan.get("budget_name") else resolve_budget(session, ctx.user_id, (state.get("intent") or {}).get("template"))
    )
    order = Order(
        user_id=ctx.user_id, objective_id=objective_id, budget_id=budget_row.id if budget_row else None, status="awaiting_approval", version=1,
        subtotal=Decimal(cart["subtotal"]), shipping=Decimal(cart["shipping_total"]), tax=Decimal(cart["tax"]),
        total=Decimal(cart["total"]), currency=cart["currency"],
    )
    for line in cart["lines"]:
        order.items.append(
            OrderItem(
                product_id=uuid.UUID(line["product"]["id"]), quantity=line["quantity"],
                unit_price=Decimal(line["unit_price"]), line_total=Decimal(line["line_total"]), reason=line["reason"],
            )
        )
    session.add(order)
    session.flush()
    from app.models import User, Workflow
    from app.services.approval import request_approval

    approval = request_approval(session, session.get(User, ctx.user_id), order, session.get(Workflow, workflow_id))
    counts = approval.details["risk"]["order"]["counts"]

    total = fmt(Decimal(cart["total"]), cart["currency"])
    ev = fin["evaluation"]
    left = fmt(Decimal(ev["remaining_after"]), cart["currency"])
    budget_name = "" if ev["budget_name"] == "request" else f" {ev['budget_name']}"
    to_decide = f" {counts['needs_decision']} item(s) need your decision first." if counts["needs_decision"] else ""
    fallback = (
        f"Your cart is ready: {len(cart['lines'])} items for {total}, leaving {left} of your{budget_name} budget."
        f"{to_decide} Nothing is bought until you approve it."
    )
    facts = (
        f"Items: {len(cart['lines'])}. Total: {total}. Budget check: {fin['evaluation']['explanation']} "
        f"Skipped: {', '.join(s['need'] for s in cart['skipped']) or 'none'}. Items needing the user's decision before approval: {counts['needs_decision']}."
    )
    message, used_llm = get_llm().write(
        "In two short sentences, tell the user their cart is ready, mention how many items need their decision if any, "
        "and that nothing is bought until they approve.", facts, fallback
    )
    return {
        "status": "awaiting_approval",
        "message": message,
        "result": {
            "order_id": str(order.id), "approval_id": str(approval.id), "cart": cart, "financial": fin,
            "risk_counts": counts, "message_by_llm": used_llm,
        },
    }
