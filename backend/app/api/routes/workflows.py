"""Workflows: start one from a request, read its state, and stream its timeline."""

import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.supervisor import PLAN
from app.api.dependencies.user import current_user
from app.core.database import get_session, get_session_factory
from app.models import AgentRun, User, Workflow
from app.orchestration.runner import run_workflow, start_workflow
from app.schemas.agents import AgentRunOut, WorkflowOut, WorkflowStart, WorkflowSummary

router = APIRouter(prefix="/workflows", tags=["workflows"])

TERMINAL = {"awaiting_approval", "needs_input", "blocked", "failed", "approved", "rejected"}
STREAM_SECONDS = 120
POLL_SECONDS = 0.4


def _to_out(session: Session, wf: Workflow) -> WorkflowOut:
    runs = session.scalars(select(AgentRun).where(AgentRun.workflow_id == wf.id).order_by(AgentRun.started_at))
    outcome = wf.state.get("outcome") or {}
    plan_run = (wf.state.get("runs") or {}).get("supervisor_plan", {})
    return WorkflowOut(
        id=wf.id,
        objective_id=wf.objective_id,
        status=wf.status,
        objective=wf.state["intent"]["objective"],
        message=outcome.get("message") or "Working on it.",
        intent=wf.state["intent"],
        plan=(plan_run.get("result") or {}).get("plan") or PLAN,
        runs=[
            AgentRunOut(
                id=r.id, agent_name=r.agent_name, status=r.status, explanation=r.explanation, output=r.output,
                started_at=r.started_at, finished_at=r.finished_at,
                duration_ms=int((r.finished_at - r.started_at).total_seconds() * 1000) if r.finished_at else None,
            )
            for r in runs
        ],
        result=outcome.get("result") or {},
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _own(session: Session, user: User, workflow_id: uuid.UUID) -> Workflow:
    wf = session.get(Workflow, workflow_id)
    if wf is None or wf.user_id != user.id:
        raise HTTPException(404, "Workflow not found")
    return wf


@router.post("", response_model=WorkflowOut, status_code=201)
def start(
    data: WorkflowStart,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    factory: sessionmaker = Depends(get_session_factory),
) -> WorkflowOut:
    wf = start_workflow(session, user, data.message)
    background.add_task(run_workflow, factory, wf.id)
    return _to_out(session, wf)


@router.get("", response_model=list[WorkflowSummary])
def recent(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[WorkflowSummary]:
    rows = session.scalars(select(Workflow).where(Workflow.user_id == user.id).order_by(Workflow.created_at.desc()).limit(20))
    out = []
    for wf in rows:
        outcome = wf.state.get("outcome") or {}
        cart = (outcome.get("result") or {}).get("cart") or {}
        out.append(
            WorkflowSummary(
                id=wf.id, objective_id=wf.objective_id, status=wf.status, objective=wf.state["intent"]["objective"], message=outcome.get("message") or "Working on it.",
                total=cart.get("total"), currency=cart.get("currency"), created_at=wf.created_at,
            )
        )
    return out


@router.get("/{workflow_id}", response_model=WorkflowOut)
def detail(workflow_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> WorkflowOut:
    return _to_out(session, _own(session, user, workflow_id))


@router.get("/{workflow_id}/events")
def events(
    workflow_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    factory: sessionmaker = Depends(get_session_factory),
) -> StreamingResponse:
    """Server-Sent Events: one `update` event whenever an agent starts or finishes, then `done`."""
    _own(session, user, workflow_id)

    def stream() -> Iterator[str]:
        last = None
        deadline = time.monotonic() + STREAM_SECONDS
        while time.monotonic() < deadline:
            with factory() as s:
                wf = s.get(Workflow, workflow_id)
                snapshot = _to_out(s, wf).model_dump(mode="json")
            key = (snapshot["status"], tuple((r["agent_name"], r["status"]) for r in snapshot["runs"]))
            if key != last:
                last = key
                yield f"event: update\ndata: {json.dumps(snapshot)}\n\n"
            if snapshot["status"] in TERMINAL:
                yield "event: done\ndata: {}\n\n"
                return
            time.sleep(POLL_SECONDS)
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
