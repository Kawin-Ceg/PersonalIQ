"""Purchases and Decision Receipts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import Order, User
from app.services import receipt as svc

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
def list_orders(user: User = Depends(current_user), session: Session = Depends(get_session)) -> list[dict]:
    """Orders past the proposal stage (approved, paying, paid, failed, cancelled)."""
    return svc.purchases(session, user)


@router.get("/{order_id}/receipt")
def receipt(order_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    order = session.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    return svc.build(session, user, order)
