"""Financial Intelligence: spending, budgets, forecast and affordability. Numbers are computed, never generated."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import User
from app.services import finance as svc

router = APIRouter(prefix="/finance", tags=["finance"])


class AffordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)  # in the user's currency
    budget_name: str | None = Field(None, max_length=120)


@router.get("/overview")
def overview(user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return svc.overview(session, user)


@router.get("/summary")
def summary(user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """A short written summary of the overview. Written by the LLM from the computed facts, or a fixed fallback."""
    data = svc.overview(session, user)
    if not data["has_data"]:
        return {"text": "", "by_llm": False}
    text, by_llm = svc.explain(data)
    return {"text": text, "by_llm": by_llm}


@router.post("/affordability")
def affordability(data: AffordIn, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    try:
        return svc.affordability(session, user, data.amount, data.budget_name)
    except svc.AffordabilityError as e:
        raise HTTPException(404, str(e))
