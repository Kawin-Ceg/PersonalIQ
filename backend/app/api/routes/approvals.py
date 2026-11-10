"""Approval Center API. Every action re-checks the approval server-side; the browser's view is never trusted."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import Approval, Order, User
from app.services import approval as svc

router = APIRouter(prefix="/approvals", tags=["approvals"])

# Refusal code -> HTTP status
STATUS = {"expired": 410, "not_pending": 409, "changed": 409, "stale": 409, "decisions_needed": 409, "over_budget": 409,
          "not_found": 404, "last_item": 422, "invalid_swap": 422, "bad_action": 422}


class ItemAction(BaseModel):
    action: Literal["keep", "remove", "swap"]
    product_id: uuid.UUID | None = None


class ApproveIn(BaseModel):
    order_hash: str = Field(min_length=64, max_length=64)  # the version the user actually looked at


class RejectIn(BaseModel):
    reason: Literal["too_expensive", "wrong_items", "not_now", "other"] | None = None


def _own(session: Session, user: User, approval_id: uuid.UUID) -> Approval:
    a = session.get(Approval, approval_id)
    if a is None or session.get(Order, a.order_id).user_id != user.id:
        raise HTTPException(404, "Approval not found")
    return a


def _run(fn):
    try:
        return fn()
    except svc.ApprovalError as e:
        raise HTTPException(STATUS.get(e.code, 400), {"code": e.code, "message": e.message})


@router.get("")
def pending(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[dict]:
    out = []
    for a in svc.pending_for(session, user):
        order = session.get(Order, a.order_id)
        counts = a.details.get("risk", {}).get("order", {}).get("counts", {})
        wf = svc._workflow(session, order)
        out.append({
            "id": str(a.id), "objective": wf.state["intent"]["objective"] if wf else "", "total": f"{order.total:.2f}",
            "currency": order.currency, "items": len(order.items), "counts": counts,
            "needs_decision_left": len(svc.pending_decisions(a)), "expires_at": svc._aware(a.expires_at).isoformat(),
        })
    return out


@router.get("/count")
def count(user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return {"pending": svc.count_pending(session, user)}


@router.get("/{approval_id}")
def detail(approval_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return svc.view(session, user, _own(session, user, approval_id))


@router.post("/{approval_id}/items/{item_id}")
def item_action(approval_id: uuid.UUID, item_id: uuid.UUID, data: ItemAction, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    a = _own(session, user, approval_id)
    result = _run(lambda: svc.act_on_item(session, user, a, item_id, data.action, data.product_id))
    return svc.view(session, user, result)  # may be a NEW approval if the order changed


@router.post("/{approval_id}/approve")
def approve(approval_id: uuid.UUID, data: ApproveIn, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    a = _own(session, user, approval_id)
    return svc.view(session, user, _run(lambda: svc.approve(session, user, a, data.order_hash)))


@router.post("/{approval_id}/reject")
def reject(approval_id: uuid.UUID, data: RejectIn, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    a = _own(session, user, approval_id)
    return svc.view(session, user, _run(lambda: svc.reject(session, user, a, data.reason)))
