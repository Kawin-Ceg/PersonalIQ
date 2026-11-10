"""Conversational front door. Understands a request, asks a follow-up if something essential is
missing, otherwise starts the purchase workflow.

Who decides what:
  Nemotron  suggests the structure (template, items, deadline) and phrases the follow-up question
  code      validates that structure, reads the budget, and decides whether a question is needed
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.llm import get_llm
from app.models import Conversation, Message, User, Workflow
from app.orchestration.runner import start_workflow
from app.schemas.agents import Intent
from app.services.budget import resolve_budget
from app.services.catalog import search_products
from app.services.fx import fmt
from app.services.intent import understand
from app.services.ranking import need_of

MAX_QUESTIONS = 2
ITEM_SUGGESTIONS = ["Furniture and basics for a new apartment", "Kitchen basics", "A home office setup", "An office chair"]
TEMPLATE_LABEL = {"apartment": "your apartment setup", "kitchen": "your kitchen", "office": "your home office", "bedroom": "your bedroom", "cleaning": "a cleaning kit"}


@dataclass
class ChatTurn:
    conversation: Conversation
    reply: str
    status: str  # clarifying | started
    intent: Intent
    workflow: Workflow | None = None
    suggestions: list[str] = field(default_factory=list)


def _missing(session: Session, user: User, intent: Intent) -> str | None:
    if not intent.needs and not intent.template:
        return "items"
    if intent.budget is None and resolve_budget(session, user.id, intent.template) is None:
        return "budget"
    return None


def _budget_suggestions(currency: str) -> list[str]:
    amounts = {"INR": [25_000, 75_000, 150_000], "SEK": [3_000, 8_000, 15_000]}.get(currency, [300, 1_000, 2_000])
    return [f"Up to {fmt(a, currency).removesuffix('.00')}" for a in amounts]


def handle_message(session: Session, user: User, text: str, conversation: Conversation | None) -> ChatTurn:
    conv = conversation or Conversation(user_id=user.id, title=text.strip()[:200], state={})
    session.add(conv)
    session.flush()
    session.add(Message(conversation_id=conv.id, role="user", content=text.strip()))

    # An answer to our question is read together with the original request.
    pending = (conv.state or {}).get("pending")
    rounds = (conv.state or {}).get("rounds", 0)
    combined = f"{pending}. {text.strip()}" if pending else text.strip()

    known = {need_of(p) for p in search_products(session)}
    intent = understand(combined, user.currency, get_llm(), known)
    missing = _missing(session, user, intent)

    if missing and rounds < MAX_QUESTIONS:
        if missing == "items":
            reply = intent.question or "What would you like PersonalIQ to get? A room to set up, or a specific item?"
            suggestions = ITEM_SUGGESTIONS
        else:
            reply = "How much would you like to spend in total?"
            suggestions = _budget_suggestions(user.currency)
        conv.state = {"pending": combined, "rounds": rounds + 1}
        turn = ChatTurn(conv, reply, "clarifying", intent, suggestions=suggestions)
    else:
        wf = start_workflow(session, user, combined, intent)
        conv.state = {}
        named = [n.need.replace("_", " ") for n in intent.needs]
        what = (", ".join(named[:-1]) + " and " + named[-1] if len(named) > 1 else named[0]) if named else TEMPLATE_LABEL.get(intent.template or "", "this")
        what = what if not named else f"your {what}"
        budget = f" with a budget of {fmt(intent.budget, user.currency)}" if intent.budget is not None else ""
        reply = f"On it. Planning {what}{budget}. You can watch each step in Activity."
        turn = ChatTurn(conv, reply, "started", intent, workflow=wf)

    session.add(
        Message(
            conversation_id=conv.id, role="assistant", content=turn.reply,
            meta={
                "status": turn.status,
                "workflow_id": str(turn.workflow.id) if turn.workflow else None,
                "suggestions": turn.suggestions,
                "understood": intent.model_dump(mode="json"),
            },
        )
    )
    session.commit()
    return turn
