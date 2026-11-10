"""The demo reset wipes everything and seeds a fresh demo."""

from decimal import Decimal

from sqlalchemy import select

from app.models import Order, Product, User
from app.seed.reset import counts, reset


def test_reset_wipes_and_reseeds(factory, session):
    priya = session.scalar(select(User).where(User.email.like("priya%")))
    session.add(Order(user_id=priya.id, status="paid", subtotal=Decimal("1"), shipping=Decimal("0"), tax=Decimal("0"), total=Decimal("1"), currency="INR"))
    session.commit()

    result = reset(engine=factory.kw["bind"], make_session=factory)
    after = counts(factory)
    assert result["users"] == 2 and after["orders"] == 0 and after["users"] == 2 and after["products"] == 44
    with factory() as s:
        assert s.scalar(select(User).where(User.email == "priya@demo.personaliq.app")) is not None
        assert s.scalar(select(Product).limit(1)) is not None
