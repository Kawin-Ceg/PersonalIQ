"""Chat: the conversational way to start (and clarify) a request."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies.user import current_user
from app.core.database import get_session, get_session_factory
from app.models import Conversation, Message, User
from app.orchestration.runner import run_workflow
from app.services.chat import handle_message

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=1000)


class ChatOut(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    status: str  # clarifying | started
    workflow_id: uuid.UUID | None
    suggestions: list[str]
    understood: dict[str, Any]  # what PersonalIQ took from the request, shown to the user for transparency


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    meta: dict[str, Any]
    sent_at: datetime


@router.post("", response_model=ChatOut)
def send(
    data: ChatIn,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    factory: sessionmaker = Depends(get_session_factory),
) -> ChatOut:
    conv = None
    if data.conversation_id:
        conv = session.get(Conversation, data.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
    turn = handle_message(session, user, data.message, conv)
    if turn.workflow:
        background.add_task(run_workflow, factory, turn.workflow.id)
    return ChatOut(
        conversation_id=turn.conversation.id,
        reply=turn.reply,
        status=turn.status,
        workflow_id=turn.workflow.id if turn.workflow else None,
        suggestions=turn.suggestions,
        understood=turn.intent.model_dump(mode="json"),
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def messages(conversation_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)):
    conv = session.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    rows = session.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.sent_at))
    return [MessageOut(id=m.id, role=m.role, content=m.content, meta=m.meta, sent_at=m.sent_at) for m in rows]
