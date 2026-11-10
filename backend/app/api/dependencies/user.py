"""Current user. No auth in the hackathon build: the frontend sends a demo user's id in X-PersonalIQ-User.
Falls back to the first demo user so the API is usable from a browser or curl."""

import uuid

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import User


def current_user(
    x_personaliq_user: str | None = Header(None),
    user: str | None = Query(None, description="Same as X-PersonalIQ-User, for EventSource which can't send headers"),
    session: Session = Depends(get_session),
) -> User:
    x_personaliq_user = x_personaliq_user or user
    if x_personaliq_user:
        try:
            user = session.get(User, uuid.UUID(x_personaliq_user))
        except ValueError:
            user = None
        if user is None:
            raise HTTPException(404, "Unknown user")
        return user
    user = session.scalar(select(User).order_by(User.email).limit(1))  # "priya@" sorts first
    if user is None:
        raise HTTPException(404, "No users seeded. Run python -m app.seed.run")
    return user
