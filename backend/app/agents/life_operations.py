"""Life Operations agent: turns an objective into requirements (needs), a task plan with
dependencies, and due dates worked backwards from the target date. Deterministic."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.schemas.agents import AgentResult, AgentTask, Intent, NeedSpec
from app.schemas.personal import UserContext
from app.services.catalog import search_products
from app.services.intent import template_needs
from app.services.ranking import need_of

TEMPLATE_LABEL = {
    "apartment": "apartment setup",
    "kitchen": "kitchen setup",
    "office": "home office setup",
    "bedroom": "bedroom setup",
    "cleaning": "cleaning kit",
}


def run(task: AgentTask, session: Session, ctx: UserContext) -> AgentResult:
    intent = Intent.model_validate(task.context["intent"])
    known = {need_of(p) for p in search_products(session)}

    # Start from the template, then make anything the user named explicitly a must-have.
    # If they named specific items, the template only adds nice-to-haves: "a chair for my home
    # office" must not turn a desk into a must-have.
    named_items = bool(intent.needs)
    needs: dict[str, NeedSpec] = {
        n.need: n.model_copy(update={"required": n.required and not named_items}) for n in template_needs(intent.template)
    }
    for n in intent.needs:
        needs[n.need] = NeedSpec(need=n.need, required=True, quantity=n.quantity)
    unknown = [n for n in needs if n not in known]
    for n in unknown:
        needs.pop(n)

    if not needs:
        return AgentResult(
            task_id=task.task_id,
            status="needs_input",
            result={"question": "What would you like PersonalIQ to get? For example: furniture for a new apartment, or an office chair."},
            explanation="I couldn't tell which items you need from the request.",
        )

    must = [n for n in needs.values() if n.required]
    nice = [n for n in needs.values() if not n.required]
    today = date.today()
    tasks, warnings = task_plan(intent.template, intent.deadline, today)
    label = TEMPLATE_LABEL.get(intent.template or "", "your request")
    explanation = f"Planned {label}: {len(must)} must-have and {len(nice)} nice-to-have items, {len(tasks)} tasks."
    if intent.deadline:
        explanation += f" Target date {intent.deadline:%d %b %Y}."
    if warnings:
        explanation += " " + warnings[0]
    return AgentResult(
        task_id=task.task_id,
        status="completed",
        result={
            "needs": [n.model_dump() for n in needs.values()],
            "tasks": tasks,
            "warnings": warnings,
            "deadline": intent.deadline.isoformat() if intent.deadline else None,
            "template": intent.template,
        },
        explanation=explanation,
    )


# ---------- the task plan ----------

DELIVERY_DAYS = 7  # ASSUMED: the demo catalog has no delivery estimates
BUFFER_DAYS = 2  # deliveries should land a couple of days before the target date
EXTERNAL = "PersonalIQ can't do this for you: there's no integration for it. It's on the list so nothing is forgotten."

# Purchase steps. owner = who does the work; tracking "auto" = PersonalIQ ticks it from real events.
PURCHASE = [
    ("needs", "Work out what you need", "life_operations", "auto", [], "Turned your request into a list of must-have and nice-to-have items."),
    ("research", "Compare products for each item", "consumer_buyer", "auto", [], "Ranks the catalog for you, leaving out what doesn't fit your preferences."),
    ("cart", "Fit the cart to the budget", "procurement", "auto", ["needs", "research"], "Picks the best combination that stays within budget, shipping included."),
    ("budget", "Check it against your budget", "financial", "auto", ["cart"], "Exact budget check before anything is shown to you."),
    ("approve", "Approve the order", "you", "auto", ["budget"], "Nothing is bought until you approve the exact order."),
    ("pay", "Pay with PayPal", "you", "auto", ["approve"], "Marked done only when PayPal confirms the payment."),
    ("deliveries", "Receive the deliveries", "you", "manual", ["pay"], "Tick this when everything has arrived. Delivery tracking isn't available for the demo catalog."),
    ("returns", "Check everything before return windows close", "you", "manual", ["deliveries"], "The receipt lists each item's return-by date."),
    ("feedback", "Rate how things worked out", "post_purchase", "auto", ["deliveries"], "Done when every item is rated. Ratings change future picks."),
]

# Things a move needs that PersonalIQ can't book. (key, title, depends_on, days relative to the target date)
LIFE_TASKS = {
    "apartment": [
        ("address", "Make sure deliveries go to the new address", [], -(DELIVERY_DAYS + BUFFER_DAYS)),
        ("movers", "Book movers", [], -14),
        ("utilities", "Set up electricity and internet at the new place", [], -7),
        ("notify", "Tell your bank and services about the new address", [], 14),
    ],
}


def task_plan(template: str | None, deadline: date | None, today: date) -> tuple[list[dict], list[str]]:
    """Ordered tasks with dependencies and, when there's a target date, due dates worked backwards."""
    order_by = deadline - timedelta(days=DELIVERY_DAYS + BUFFER_DAYS) if deadline else None
    due = {"approve": order_by, "pay": order_by, "deliveries": deadline - timedelta(days=BUFFER_DAYS) if deadline else None}

    tasks = []
    life = LIFE_TASKS.get(template or "", [])
    for key, title, deps, offset in life:
        tasks.append({
            "key": key, "title": title, "owner": "you", "tracking": "manual", "external": True, "depends_on": deps,
            "due_on": (deadline + timedelta(days=offset)).isoformat() if deadline else None, "detail": EXTERNAL,
        })
    for key, title, owner, tracking, deps, detail in PURCHASE:
        if key == "pay" and life:
            deps = [*deps, "address"]  # orders should ship to the new place
        tasks.append({
            "key": key, "title": title, "owner": owner, "tracking": tracking, "external": False, "depends_on": deps,
            "due_on": due[key].isoformat() if due.get(key) else None, "detail": detail,
        })

    warnings = []
    if deadline and order_by is not None and order_by < today:
        warnings.append(
            f"Tight timeline: to arrive by {deadline:%d %b}, orders should have gone out by {order_by:%d %b}. "
            f"Delivery time is assumed to be {DELIVERY_DAYS} days."
        )
    elif deadline:
        warnings.append(f"Approve and pay by {order_by:%d %b} so deliveries arrive in time (assumes {DELIVERY_DAYS}-day delivery).")
    return tasks, warnings
