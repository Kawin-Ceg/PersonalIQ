import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base, get_session, get_session_factory
from app.main import app
from app.seed.run import seed

# SQLite has no native decimal; SQLAlchemy warns but values still round-trip as Decimal.
warnings.filterwarnings("ignore", message=".*Dialect sqlite.*Decimal.*")


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Tests never call a paid LLM API, even if a key is in .env: every agent gets the stand-in."""
    from app.agents import llm

    stub = llm.LLM.__new__(llm.LLM)
    stub.model, stub.provider, stub._client = "stub", "stub", None
    # Patch every module that imported get_llm by name.
    for target in ("app.agents.llm", "app.agents.supervisor", "app.services.chat"):
        monkeypatch.setattr(f"{target}.get_llm", lambda: stub)
    # Belt and braces: even a direct LLM() in a test gets no client.
    monkeypatch.setattr(llm.LLM, "available", property(lambda self: False))


@pytest.fixture
def factory(tmp_path):
    """A fresh SQLite file per test. A file (not :memory:) so parallel agents get their own connections."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 15})
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as s:
        seed(s)
    yield maker
    engine.dispose()


@pytest.fixture
def session(factory):
    with factory() as s:
        yield s


@pytest.fixture
def client(factory, session):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_session_factory] = lambda: factory
    yield TestClient(app)
    app.dependency_overrides.clear()
