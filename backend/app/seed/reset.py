"""Reset the demo: delete ALL PersonalIQ data in the configured database, then seed it again.

    python -m app.seed.reset          # shows what would be deleted, changes nothing
    python -m app.seed.reset --yes    # deletes and re-seeds

Use it before a demo: Priya's Apartment move budget is back to ₹1,69,000 with nothing spent, and
the catalog, demo users, memories, spending history and reviews are fresh. Sandbox payments
already made at PayPal are not touched (only our local records of them are removed).
"""

import sys

from sqlalchemy import func, select, text

import app.models  # noqa: F401 (registers every table)
from app.core.database import Base, get_engine, new_session
from app.seed.run import seed


def counts(make_session=new_session) -> dict[str, int]:
    with make_session() as s:
        return {t.name: s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}


def reset(engine=None, make_session=new_session) -> dict:
    engine = engine or get_engine()
    if engine is None:
        raise SystemExit("DATABASE_URL is not set.")
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        else:  # SQLite (tests): delete children first
            for t in reversed(Base.metadata.sorted_tables):
                conn.execute(t.delete())
    with make_session() as s:
        return seed(s)


def main(argv: list[str]) -> int:
    before = {k: v for k, v in counts().items() if v}
    print("This deletes all PersonalIQ data in the configured database:")
    for name, n in sorted(before.items()):
        print(f"  {name:16} {n} rows")
    if "--yes" not in argv:
        print("\nNothing changed. Run again with --yes to reset.")
        return 1
    print("\nReset done. Seeded:", reset())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
