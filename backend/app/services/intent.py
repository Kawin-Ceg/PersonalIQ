"""Rule-based intent parser. Deterministic and always available.

Feature 5 puts Nemotron in front of this; when the LLM is unavailable or unsure, this is the
fallback. It extracts: a budget (with currency), a known template ("apartment", "kitchen", ...),
items the user named explicitly, and a rough deadline.
"""

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.schemas.agents import Intent, NeedSpec
from app.services.fx import RATES, convert, fmt

# Words people use -> catalog need. Longer phrases are checked first.
NEED_WORDS: dict[str, str] = {
    "office chair": "office_chair", "desk chair": "office_chair", "chair": "office_chair",
    "standing desk": "desk", "desk": "desk",
    "mattress": "mattress", "bed frame": "bed_frame", "bed": "bed_frame",
    "sofa": "sofa", "couch": "sofa", "loveseat": "sofa",
    "dining table": "dining", "dining": "dining", "table": "dining",
    "bookcase": "storage", "bookshelf": "storage", "shelf": "storage",
    "cookware": "cookware", "pots": "cookware", "pans": "cookware",
    "microwave": "microwave", "kettle": "kettle", "coffee": "coffee", "knife": "knives", "knives": "knives",
    "dinnerware": "dinnerware", "plates": "dinnerware", "dishes": "dinnerware",
    "blender": "blender", "toaster": "toaster",
    "tv": "tv", "television": "tv", "router": "router", "wifi": "router", "wi-fi": "router",
    "lamp": "lighting", "light": "lighting", "surge protector": "power", "power strip": "power",
    "vacuum": "vacuum", "mop": "mop", "cleaning supplies": "supplies", "trash can": "trash", "bin": "trash",
    "sheets": "sheets", "comforter": "comforter", "duvet": "comforter", "pillow": "pillows", "pillows": "pillows",
    "towel": "towels", "towels": "towels", "curtains": "curtains", "tool kit": "tools", "tools": "tools",
    "hangers": "hangers", "first aid": "first_aid",
}

# Templates: (keywords, [(need, required)])
TEMPLATES: dict[str, tuple[tuple[str, ...], list[tuple[str, bool]]]] = {
    "apartment": (
        ("apartment", "flat", "moving", "move in", "new home", "new place", "relocat"),
        [("mattress", True), ("bed_frame", True), ("sheets", True), ("pillows", True), ("cookware", True),
         ("sofa", False), ("dining", False), ("desk", False), ("office_chair", False), ("microwave", False),
         ("kettle", False), ("vacuum", False), ("towels", False), ("curtains", False)],
    ),
    "kitchen": (
        ("kitchen", "cooking", "cook "),
        [("cookware", True), ("knives", True), ("dinnerware", True), ("kettle", False), ("microwave", False),
         ("toaster", False), ("blender", False), ("coffee", False)],
    ),
    "office": (
        ("home office", "work from home", "wfh", "workspace", "study setup"),
        [("desk", True), ("office_chair", True), ("lighting", False), ("router", False), ("power", False)],
    ),
    "bedroom": (
        ("bedroom", "sleep setup"),
        [("mattress", True), ("bed_frame", True), ("sheets", True), ("pillows", True), ("comforter", False), ("curtains", False)],
    ),
    "cleaning": (
        ("cleaning", "clean the", "clean my"),
        [("vacuum", True), ("mop", False), ("supplies", True), ("trash", False)],
    ),
}

CURRENCY_HINTS = [
    (r"₹|\brs\.?|\binr\b|\brupees?\b|\blakh|\blac\b|\bcrore", "INR"),
    (r"\$|\busd\b|\bdollars?\b", "USD"),
    (r"€|\beur\b|\beuros?\b", "EUR"),
    (r"£|\bgbp\b|\bpounds?\b", "GBP"),
    (r"\bkr\b|\bsek\b|\bkronor\b", "SEK"),
]
MULTIPLIER = {"k": Decimal(1_000), "thousand": Decimal(1_000), "lakh": Decimal(100_000), "lakhs": Decimal(100_000),
              "lac": Decimal(100_000), "l": Decimal(100_000), "crore": Decimal(10_000_000), "m": Decimal(1_000_000)}

AMOUNT = re.compile(
    r"(?P<sym>₹|\$|€|£)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|lakhs?|lac|l|crore|m)?\b\s*(?P<code>inr|usd|eur|gbp|sek|kr|rs|rupees?|dollars?|euros?|pounds?)?",
    re.IGNORECASE,
)


def _budget(text: str, user_currency: str) -> tuple[Decimal | None, str | None]:
    best = None
    for m in AMOUNT.finditer(text):
        try:
            value = Decimal(m.group("num").replace(",", ""))
        except InvalidOperation:
            continue
        mult = (m.group("mult") or "").lower()
        if mult:
            value *= MULTIPLIER.get(mult, Decimal(1))
        has_money_marker = m.group("sym") or m.group("code") or mult
        near_word = re.search(r"(budget|under|below|within|max|upto|up to|spend|less than)\s*\S*\s*$", text[: m.start()], re.IGNORECASE)
        if not (has_money_marker or near_word) or value < 1:
            continue  # "2 people", "13 gallon" are not budgets
        if not m.group("sym") and re.match(r"\s*(minutes?|hours?|days?|weeks?|months?|years?|yrs?)\b", text[m.end("num"):], re.IGNORECASE):
            continue  # "within 3 weeks" is a deadline, not money
        if best is None or value > best[0]:
            best = (value, m.group(0))
    if best is None:
        return None, None
    amount, raw = best
    currency = next((c for pattern, c in CURRENCY_HINTS if re.search(pattern, raw, re.IGNORECASE)), None)
    if currency is None or currency not in RATES:
        return amount.quantize(Decimal("0.01")), None
    if currency == user_currency:
        return amount.quantize(Decimal("0.01")), None
    converted = convert(amount, currency, user_currency)
    return converted, f"Converted from {fmt(amount, currency)} at the fixed demo rate."


def _deadline(text: str, today: date) -> date | None:
    t = text.lower()
    if "next week" in t:
        return today + timedelta(days=7)
    if "next month" in t:
        return today + timedelta(days=30)
    m = re.search(r"in (\d{1,2}) (day|week|month)s?", t)
    if m:
        n = int(m.group(1))
        return today + timedelta(days=n * {"day": 1, "week": 7, "month": 30}[m.group(2)])
    # "by 15 December", "by Dec 15", "before 3 jan": this year, or next year if already past.
    months = "jan feb mar apr may jun jul aug sep oct nov dec".split()
    m = re.search(r"(?:by|before|on) (\d{1,2})(?:st|nd|rd|th)? (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", t) or         re.search(r"(?:by|before|on) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* (\d{1,2})(?:st|nd|rd|th)?", t)
    if m:
        a, b = m.groups()
        day_s, mon = (a, b) if a.isdigit() else (b, a)
        try:
            d = date(today.year, months.index(mon) + 1, int(day_s))
        except ValueError:
            return None
        return d if d >= today else date(today.year + 1, d.month, d.day)
    return None


def parse_intent(message: str, user_currency: str, today: date | None = None) -> Intent:
    text = " " + message.strip().lower() + " "
    template = next((name for name, (words, _) in TEMPLATES.items() if any(w in text for w in words)), None)

    named: list[str] = []
    remaining = text
    for phrase in sorted(NEED_WORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}s?\b", remaining):
            need = NEED_WORDS[phrase]
            if need not in named:
                named.append(need)
            remaining = re.sub(rf"\b{re.escape(phrase)}s?\b", " ", remaining)

    budget, note = _budget(message, user_currency)
    objective = message.strip().rstrip(".!?")
    return Intent(
        message=message.strip(),
        objective=objective[:120],
        template=template,
        needs=[NeedSpec(need=n, required=True) for n in named],
        budget=budget,
        currency=user_currency,
        budget_note=note,
        deadline=_deadline(message, today or date.today()),
    )


def template_needs(template: str | None) -> list[NeedSpec]:
    if not template:
        return []
    return [NeedSpec(need=n, required=r) for n, r in TEMPLATES[template][1]]


# ---------- Nemotron in front, rules behind ----------

UNDERSTAND_PROMPT = """Turn the shopping request into JSON with exactly these keys:
  "objective": short title of the goal, max 8 words
  "template": one of {templates} or null
  "needs": list of {{"need": <one of the allowed needs>, "required": true|false}} for items the person asked for
  "deadline_days": number of days until they need it, or null
  "clarifying_question": one short question if it is unclear WHAT to buy, else null
Allowed needs: {needs}
Do not include prices or budgets. Use only allowed values."""


def understand(message: str, user_currency: str, llm, known_needs: set[str], today: date | None = None) -> Intent:
    """Nemotron reads the request; code validates every field. Money always comes from the rules."""
    rules = parse_intent(message, user_currency, today)
    if not getattr(llm, "available", False):
        return rules
    data = llm.extract_json(UNDERSTAND_PROMPT.format(templates=", ".join(TEMPLATES), needs=", ".join(sorted(known_needs))), message)
    if not data:
        return rules

    template = data.get("template") if data.get("template") in TEMPLATES else rules.template
    needs = {n.need: n for n in rules.needs}  # keyword matches are reliable; keep them
    for item in data.get("needs") or []:
        if isinstance(item, dict) and item.get("need") in known_needs and item["need"] not in needs:
            needs[item["need"]] = NeedSpec(need=item["need"], required=bool(item.get("required", True)))
    days = data.get("deadline_days")
    deadline = (today or date.today()) + timedelta(days=days) if isinstance(days, int) and 0 < days <= 365 else rules.deadline
    objective = data.get("objective") if isinstance(data.get("objective"), str) and data["objective"].strip() else rules.objective
    question = data.get("clarifying_question") if isinstance(data.get("clarifying_question"), str) else None

    return rules.model_copy(
        update={
            "objective": objective.strip()[:120],
            "template": template,
            "needs": list(needs.values()),
            "deadline": deadline,
            "understood_by": "nemotron",
            "question": (question or "").strip()[:200] or None,
        }
    )
