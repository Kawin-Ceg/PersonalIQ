"""The learning loop, made visible: record a rating, then show exactly what it changed.

Ranks the rated product's need before and after, with the same deterministic ranking the
agents use, and diffs the weights and the order. Nothing here is estimated or written by an LLM.
"""

from sqlalchemy.orm import Session

from app.models import Feedback, Memory, Product, User
from app.schemas.personal import FeedbackIn
from app.services.catalog import search_products
from app.services.memory import list_memories
from app.services.personal_intelligence import build_user_context, record_feedback
from app.services.ranking import need_of, rank_products, weights_for

WEIGHT_LABEL = {"quality": "Quality", "value": "Value for money", "price": "Price", "durability": "Durability", "fit": "Fit"}


def _snapshot(session: Session, user: User, need: str) -> tuple[dict, dict[str, dict]]:
    ctx = build_user_context(session, user)
    products = [p for p in search_products(session) if need_of(p) == need]
    ranking = rank_products(session, products, ctx)
    ranked = {str(s.product.id): {"name": s.product.name, "rank": s.rank, "score": s.score} for s in ranking.ranked}
    for p, reasons in ranking.excluded:
        ranked[str(p.id)] = {"name": p.name, "rank": None, "score": None, "excluded": reasons}
    return ctx, ranked


def _memory_state(memories: list[Memory]) -> dict[str, tuple[str, str]]:
    return {m.meta.get("key", str(m.id)): (m.content, m.source) for m in memories}


def record_with_impact(session: Session, user: User, data: FeedbackIn) -> tuple[Feedback, dict | None]:
    product = session.get(Product, data.product_id) if data.product_id else None
    if product is None:
        return record_feedback(session, user, data), None  # an item outside the catalog teaches lessons, not rankings

    need, category = need_of(product), product.category
    before_ctx, before = _snapshot(session, user, need)
    before_mem = _memory_state(list_memories(session, user.id))

    fb = record_feedback(session, user, data)  # validates and commits

    after_ctx, after = _snapshot(session, user, need)
    after_mem = list_memories(session, user.id)
    learned = [
        {"content": m.content, "source": m.source, "confidence": m.confidence, "memory_id": str(m.id)}
        for m in after_mem
        if before_mem.get(m.meta.get("key", str(m.id))) != (m.content, m.source)
    ]

    wb, wa = weights_for(before_ctx, category), weights_for(after_ctx, category)
    weights = [
        {"key": k, "label": WEIGHT_LABEL[k], "before": wb[k], "after": wa[k]}
        for k in ("quality", "value", "price", "durability", "fit")
    ]

    moves = []
    for pid, a in after.items():
        b = before.get(pid, {})
        if b.get("rank") != a.get("rank") or b.get("score") != a.get("score"):
            moves.append({
                "product_id": pid, "name": a["name"], "rated": pid == str(product.id),
                "before_rank": b.get("rank"), "after_rank": a.get("rank"),
                "before_score": b.get("score"), "after_score": a.get("score"),
                "excluded": a.get("excluded"),
            })
    moves.sort(key=lambda m: (m["after_rank"] is None, m["after_rank"] or 0))

    changed = any(w["before"] != w["after"] for w in weights) or bool(moves)
    return fb, {
        "category": category, "need": need, "changed": changed,
        "memories": learned, "weights": weights, "moves": moves[:6],
        "summary": _summary(product, fb, learned, weights, moves, category),
    }


def _summary(product: Product, fb: Feedback, learned: list, weights: list, moves: list, category: str) -> str:
    rose = [w for w in weights if w["after"] > w["before"]]
    parts = []
    if rose:
        top = max(rose, key=lambda w: w["after"] - w["before"])
        parts.append(f"{top['label']} now counts for {top['after'] * 100:.0f}% of a {category} score (was {top['before'] * 100:.0f}%).")
    rated = next((m for m in moves if m["rated"]), None)
    if rated and rated["excluded"]:
        parts.append(f"{product.name} won't be suggested again.")
    elif rated and rated["before_rank"] != rated["after_rank"]:
        parts.append(f"{product.name} moved from #{rated['before_rank']} to #{rated['after_rank']} for you.")
    if not parts:
        parts.append("Noted. This rating doesn't change future picks." if not learned else "Saved to what PersonalIQ knows about you.")
    return " ".join(parts)
