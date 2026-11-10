"""Objectives: the plan behind each request, its tasks, and progress."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import User
from app.services import objectives as svc

router = APIRouter(prefix="/objectives", tags=["objectives"])


class TaskDone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done: bool


def _run(fn):
    try:
        return fn()
    except svc.ObjectiveError as e:
        raise HTTPException(e.status, e.message)


@router.get("")
def list_objectives(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[dict]:
    return svc.summaries(session, user)


@router.get("/{objective_id}")
def detail(objective_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return _run(lambda: svc.view(session, svc.own(session, user, objective_id)))


@router.post("/{objective_id}/tasks/{task_id}")
def set_task(objective_id: uuid.UUID, task_id: uuid.UUID, data: TaskDone, user: User = Depends(current_user),
             session: Session = Depends(get_session)) -> dict:
    return _run(lambda: svc.set_done(session, user, svc.own(session, user, objective_id), task_id, data.done))
