"""Procurement agent: turns requirements + ranked candidates into the best cart within budget."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Product
from app.schemas.agents import AgentResult, AgentTask
from app.schemas.commerce import CartRequest, NeedIn
from app.schemas.personal import UserContext
from app.services.cart import optimize_cart
from app.services.catalog import search_products
from app.services.ranking import Scored


def _candidates_from_buyer(session: Session, candidates: dict, ctx_currency: str) -> dict[str, list[Scored]]:
    by_need: dict[str, list[Scored]] = {}
    for need, items in candidates.items():
        scored = []
        for c in items:
            p = session.get(Product, uuid.UUID(c["product_id"]))
            if p is not None:
                scored.append(Scored(product=p, score=c["score"], components=[], rank=c["rank"]))
        by_need[need] = scored
    return by_need


def run(task: AgentTask, session: Session, ctx: UserContext) -> AgentResult:
    needs = task.context.get("needs") or []
    if not needs:
        return AgentResult(task_id=task.task_id, status="skipped", explanation="Nothing to buy yet: waiting for the list of needs.")

    budget = Decimal(task.constraints["budget"])
    req = CartRequest(budget=budget, needs=[NeedIn(**n) for n in needs], budget_name=task.constraints.get("budget_name"))
    by_need = _candidates_from_buyer(session, task.context["candidates"], ctx.currency)
    plan = optimize_cart(session, search_products(session), ctx, req, by_need=by_need)
    return AgentResult(
        task_id=task.task_id,
        status="completed" if plan.feasible else "failed",
        result={"cart": plan.model_dump(mode="json")},
        explanation=plan.message,
        errors=[] if plan.feasible else [plan.message],
    )
