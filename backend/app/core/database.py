"""SQLAlchemy engine, session factory and declarative base."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def sync_url(url: str) -> str:
    """Accept postgres://, postgresql:// or +asyncpg URLs and use the psycopg driver."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache
def get_engine() -> Engine | None:
    url = get_settings().database_url
    if not url:
        return None
    return create_engine(sync_url(url), pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_session_factory() -> sessionmaker:
    """FastAPI dependency for work that outlives the request (background workflows, event streams)."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL is not set")
    return sessionmaker(bind=engine, expire_on_commit=False)


def new_session() -> Session:
    return get_session_factory()()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with new_session() as session:
        yield session


def database_status() -> str:
    """Returns 'ok', 'unreachable' or 'not_configured'."""
    engine = get_engine()
    if engine is None:
        return "not_configured"
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return "ok"
    except Exception:
        return "unreachable"
