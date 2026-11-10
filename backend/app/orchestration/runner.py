"""Start and run workflows. The HTTP request returns at once; the graph runs in the background."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.models import Objective, User, Workflow
from app.orchestration.graph import GRAPH, STEP_LIMIT, Deps
from app.schemas.agents import Intent
from app.services.intent import parse_intent

log = logging.getLogger(__name__)


def start_workflow(session: Session, user: User, message: str, intent: Intent | None = None) -> Workflow:
    intent = intent or parse_intent(message, user.currency)
    objective = Objective(
        user_id=user.id, title=intent.objective[:200], description=message, status="running",
        budget_limit=intent.budget, currency=user.currency, deadline=intent.deadline,
    )
    session.add(objective)
    session.flush()
    wf = Workflow(
        user_id=user.id, objective_id=objective.id, workflow_type="purchase", status="running",
        state={"intent": intent.model_dump(mode="json")},
    )
    session.add(wf)
    session.commit()
    return wf


def run_workflow(session_factory: sessionmaker, workflow_id: uuid.UUID) -> None:
    with session_factory() as s:
        wf = s.get(Workflow, workflow_id)
        user_id, intent = wf.user_id, wf.state["intent"]
    deps = Deps(session_factory=session_factory, workflow_id=workflow_id, user_id=user_id)
    try:
        GRAPH.invoke(
            {"workflow_id": str(workflow_id), "user_id": str(user_id), "intent": intent, "runs": {},
             "started_at": datetime.now(timezone.utc).isoformat(), "recovery": {}},
            config={"configurable": {"deps": deps}, "recursion_limit": STEP_LIMIT},
        )
    except Exception as e:
        log.exception("Workflow %s crashed", workflow_id)
        with session_factory() as s:
            wf = s.get(Workflow, workflow_id)
            wf.status = "failed"
            wf.state = {**wf.state, "outcome": {"status": "failed", "message": f"Something went wrong: {type(e).__name__}.", "result": {}}}
            s.commit()
