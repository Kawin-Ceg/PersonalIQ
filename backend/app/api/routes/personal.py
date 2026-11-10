"""Personal Intelligence API. Everything here is scoped to the current user."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import Feedback, Memory, User
from app.schemas.personal import (
    CsvImportIn,
    CsvImportOut,
    DemoUser,
    EventIn,
    FeedbackIn,
    FeedbackOut,
    MemoryOut,
    MemoryPatch,
    OnboardingIn,
    UserContext,
)
from app.services import learning
from app.services import personal_intelligence as pi
from app.services.memory import CONFIDENCE, list_memories

router = APIRouter(tags=["personal"])


@router.get("/users", response_model=list[DemoUser])
def demo_users(session: Session = Depends(get_session)):
    return list(session.scalars(select(User).order_by(User.email)))


@router.get("/me/context", response_model=UserContext)
def my_context(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return pi.build_user_context(session, user)


@router.post("/me/onboarding", response_model=UserContext)
def onboarding(data: OnboardingIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    pi.apply_onboarding(session, user, data)
    return pi.build_user_context(session, user)


@router.get("/me/memories", response_model=list[MemoryOut])
def memories(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return list_memories(session, user.id)


def _own_memory(session: Session, user: User, memory_id: uuid.UUID) -> Memory:
    mem = session.get(Memory, memory_id)
    if mem is None or mem.user_id != user.id:
        raise HTTPException(404, "Memory not found")
    return mem


@router.patch("/me/memories/{memory_id}", response_model=MemoryOut)
def correct_memory(
    memory_id: uuid.UUID, patch: MemoryPatch, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    """A correction from the user becomes a user-stated fact with full confidence."""
    mem = _own_memory(session, user, memory_id)
    if patch.content is not None:
        mem.content = patch.content
    if patch.level is not None:
        if "level" not in mem.meta:
            raise HTTPException(422, "This memory has no level")
        mem.meta = {**mem.meta, "level": patch.level}
        if patch.content is None:
            mem.content = pi.describe_level(mem.meta["key"], patch.level)
    mem.source = "user_stated"
    mem.confidence = CONFIDENCE["user_stated"]
    session.commit()
    return mem


@router.delete("/me/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)):
    session.delete(_own_memory(session, user, memory_id))
    session.commit()


@router.get("/me/feedback", response_model=list[FeedbackOut])
def my_feedback(user: User = Depends(current_user), session: Session = Depends(get_session)):
    stmt = select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.created_at.desc())
    return list(session.scalars(stmt))


@router.post("/me/feedback", response_model=FeedbackOut, status_code=201)
def add_feedback(data: FeedbackIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    if data.product_id is None and not (data.item_name and data.item_name.strip()):
        raise HTTPException(422, "Pick a product or name the item")
    try:
        fb, impact = learning.record_with_impact(session, user, data)
    except pi.FeedbackError as e:
        raise HTTPException(e.status, e.message)
    return FeedbackOut.model_validate(fb).model_copy(update={"learning": impact})


@router.post("/me/events", status_code=204)
def add_event(data: EventIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    pi.record_event(session, user, data.event_type, data.product_id, data.payload)


@router.post("/me/transactions/import", response_model=CsvImportOut)
def import_csv(data: CsvImportIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return pi.import_transactions_csv(session, user, data.csv)
