"""Typed contracts between the supervisor and agents. Agents never pass free text to each other."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer

AgentName = Literal["supervisor", "life_operations", "consumer_buyer", "procurement", "financial", "post_purchase"]
AgentStatus = Literal["running", "completed", "needs_input", "failed", "skipped"]
WorkflowStatus = Literal["running", "awaiting_approval", "needs_input", "blocked", "failed"]


class NeedSpec(BaseModel):
    need: str
    required: bool = True
    quantity: int = 1


class Intent(BaseModel):
    """What the user wants, in structure. Built by the intent parser (rules now, Nemotron in feature 5)."""

    message: str
    objective: str
    template: str | None = None  # apartment | kitchen | office | bedroom | cleaning
    needs: list[NeedSpec] = Field(default_factory=list)  # needs the user named explicitly
    budget: Decimal | None = None  # in the user's currency
    currency: str
    budget_note: str | None = None  # e.g. "Converted from $200 at the demo rate"
    deadline: date | None = None
    understood_by: Literal["nemotron", "rules"] = "rules"
    question: str | None = None  # Nemotron's follow-up question, if it thinks something is unclear

    @field_serializer("budget")
    def _b(self, v: Decimal | None) -> str | None:
        return None if v is None else f"{v:.2f}"


class AgentTask(BaseModel):
    task_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workflow_id: uuid.UUID
    user_id: uuid.UUID
    agent_name: AgentName
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[uuid.UUID] = Field(default_factory=list)


class AgentResult(BaseModel):
    task_id: uuid.UUID
    status: AgentStatus
    result: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    explanation: str = ""
    requires_human_approval: bool = False
    errors: list[str] = Field(default_factory=list)


# ---- API views ----


class WorkflowStart(BaseModel):
    message: str = Field(min_length=2, max_length=1000)


class AgentRunOut(BaseModel):
    id: uuid.UUID
    agent_name: str
    status: str
    explanation: str
    output: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None


class WorkflowOut(BaseModel):
    id: uuid.UUID
    objective_id: uuid.UUID | None = None
    status: str
    objective: str
    message: str  # what PersonalIQ says about the outcome
    intent: dict[str, Any]
    plan: list[dict[str, Any]]
    runs: list[AgentRunOut]
    result: dict[str, Any]  # cart plan, budget evaluation, order id
    created_at: datetime
    updated_at: datetime


class WorkflowSummary(BaseModel):
    id: uuid.UUID
    objective_id: uuid.UUID | None = None
    status: str
    objective: str
    message: str
    total: str | None
    currency: str | None
    created_at: datetime
