from decimal import Decimal

from sqlalchemy import select

from app.models import Transaction, User


def _theo(session):
    return session.scalar(select(User).where(User.email == "theo@demo.personaliq.app"))


def _ctx(client, user):
    return client.get("/api/v1/me/context", headers={"X-PersonalIQ-User": str(user.id)}).json()


def test_bad_outcome_raises_importance_but_user_correction_wins(client, session):
    theo = _theo(session)
    h = {"X-PersonalIQ-User": str(theo.id)}
    before = _ctx(client, theo)
    assert before["importance"]["durability"]["source"] == "default"

    # Feedback: a cheap chair broke. Durability should now matter more, and weigh more in scoring.
    client.post("/api/v1/me/feedback", headers=h, json={"item_name": "Old desk chair", "rating": 3, "didnt_work": "base cracked", "reasons": ["durability"]})
    after = _ctx(client, theo)
    assert after["importance"]["durability"] == {**after["importance"]["durability"], "level": "high", "source": "feedback"}
    assert after["scoring_weights"]["durability"] > before["scoring_weights"]["durability"]
    assert abs(sum(after["scoring_weights"].values()) - 1.0) < 0.01

    # Theo corrects it. Later feedback must not overwrite his correction.
    mem = next(m for m in client.get("/api/v1/me/memories", headers=h).json() if m["meta"]["key"] == "importance.durability")
    client.patch(f"/api/v1/me/memories/{mem['id']}", headers=h, json={"level": "low"})
    client.post("/api/v1/me/feedback", headers=h, json={"item_name": "Lamp", "rating": 2, "reasons": ["durability"]})
    final = _ctx(client, theo)["importance"]["durability"]
    assert (final["level"], final["source"]) == ("low", "user_stated")


def test_csv_import_parses_decimal_reports_errors_and_skips_duplicates(client, session):
    theo = _theo(session)
    h = {"X-PersonalIQ-User": str(theo.id)}
    csv = "date,merchant,category,amount\n2026-11-01,FreshCart,Groceries,64.20\nnot-a-date,X,Y,1\n2026-11-02,Bistro,Dining,1,234.50"
    first = client.post("/api/v1/me/transactions/import", headers=h, json={"csv": csv}).json()
    assert first["imported"] == 1 and len(first["errors"]) == 2  # bad date; unquoted comma breaks the row
    again = client.post("/api/v1/me/transactions/import", headers=h, json={"csv": csv}).json()
    assert again["imported"] == 0 and again["duplicates"] == 1
    tx = session.scalar(select(Transaction).where(Transaction.user_id == theo.id))
    assert tx.amount == Decimal("64.20")


def test_seeded_profile_feeds_the_context(client):
    ctx = client.get("/api/v1/me/context").json()  # defaults to Priya
    assert ctx["onboarded"] is True
    assert ctx["avoid_materials"] == ["leather"]
    assert ctx["importance"]["durability"]["source"] == "user_stated"  # her own answer, not the cookware feedback
    assert any("Nonstick" in lesson for lesson in ctx["lessons"])
    assert ctx["spending"]["transaction_count"] == 20
