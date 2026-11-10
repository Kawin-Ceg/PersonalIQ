"""Personal memory store. Every learned fact is a Memory row with a key, a source and a confidence.

Authority rule: a memory can only be replaced by a source of equal or higher authority.
So feedback can update something we observed, but nothing overwrites what the user told us.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory

AUTHORITY = {"inferred": 0, "observed": 1, "feedback": 2, "uploaded": 3, "user_stated": 4}
CONFIDENCE = {"inferred": 0.5, "observed": 0.6, "feedback": 0.8, "uploaded": 0.9, "user_stated": 1.0}


def list_memories(session: Session, user_id: uuid.UUID) -> list[Memory]:
    stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at)
    return list(session.scalars(stmt))


def by_key(memories: list[Memory]) -> dict[str, Memory]:
    return {m.meta["key"]: m for m in memories if m.meta.get("key")}


def remember(
    session: Session,
    user_id: uuid.UUID,
    key: str,
    content: str,
    memory_type: str,
    source: str,
    **extra,
) -> Memory | None:
    """Create or update the memory for `key`. Returns None if a higher-authority memory already holds it."""
    existing = session.scalar(
        select(Memory).where(Memory.user_id == user_id, Memory.meta["key"].as_string() == key)
    )
    if existing and AUTHORITY[existing.source] > AUTHORITY[source]:
        return None
    mem = existing or Memory(user_id=user_id)
    mem.memory_type = memory_type
    mem.content = content
    mem.source = source
    mem.confidence = CONFIDENCE[source]
    mem.meta = {"key": key, **extra}
    session.add(mem)
    return mem


def forget(session: Session, user_id: uuid.UUID, key_prefix: str, source: str = "user_stated") -> None:
    """Remove memories under a prefix that came from `source` (used when onboarding is re-submitted)."""
    for m in list_memories(session, user_id):
        if m.meta.get("key", "").startswith(key_prefix) and m.source == source:
            session.delete(m)
