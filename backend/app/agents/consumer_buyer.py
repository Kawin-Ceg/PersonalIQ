"""Consumer Buyer agent: researches the catalog and ranks candidates for every need.

Runs in parallel with Life Operations, so it ranks the whole catalog; Procurement later keeps
only the needs Life Operations asked for. Scoring is the deterministic ranking service.
"""

from sqlalchemy.orm import Session

from app.schemas.agents import AgentResult, AgentTask
from app.schemas.personal import UserContext
from app.services.catalog import search_products
from app.services.ranking import rank_products

TOP_PER_NEED = 4


def run(task: AgentTask, session: Session, ctx: UserContext) -> AgentResult:
    depth = int(task.constraints.get("depth") or TOP_PER_NEED)  # the supervisor asks for more when a cart won't fit
    ranking = rank_products(session, search_products(session), ctx)
    candidates = {
        need: [{"product_id": str(s.product.id), "name": s.product.name, "score": s.score, "rank": s.rank} for s in items[:depth]]
        for need, items in ranking.by_need().items()
    }
    excluded = [{"product_id": str(p.id), "name": p.name, "reasons": r} for p, r in ranking.excluded]
    return AgentResult(
        task_id=task.task_id,
        status="completed",
        result={"candidates": candidates, "excluded": excluded, "weights": ctx.scoring_weights, "category_weights": ctx.category_weights},
        explanation=(f"Ranked {len(ranking.ranked)} products across {len(candidates)} needs; left out {len(excluded)} that don't fit your preferences."
                     + (f" Deeper search: up to {depth} options per item." if depth != TOP_PER_NEED else "")),
    )
