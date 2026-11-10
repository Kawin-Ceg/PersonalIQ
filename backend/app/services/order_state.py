"""The order lifecycle. Every status change goes through `transition`, which refuses illegal moves.

draft -> awaiting_approval -> approved -> paypal_order_created -> awaiting_buyer_checkout -> capturing -> paid
                                   \\-> rejected / expired / cancelled           failed / reconciliation_required
"""

from enum import StrEnum

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Order


class OrderStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAYPAL_ORDER_CREATED = "paypal_order_created"
    AWAITING_BUYER_CHECKOUT = "awaiting_buyer_checkout"
    CAPTURING = "capturing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RECONCILIATION_REQUIRED = "reconciliation_required"


S = OrderStatus
TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.DRAFT: frozenset({S.AWAITING_APPROVAL, S.CANCELLED}),
    # awaiting_approval -> awaiting_approval: the order changed and a new version needs approving.
    S.AWAITING_APPROVAL: frozenset({S.AWAITING_APPROVAL, S.APPROVED, S.REJECTED, S.EXPIRED, S.CANCELLED}),
    S.APPROVED: frozenset({S.PAYPAL_ORDER_CREATED, S.AWAITING_APPROVAL, S.EXPIRED, S.CANCELLED}),
    S.PAYPAL_ORDER_CREATED: frozenset({S.AWAITING_BUYER_CHECKOUT, S.FAILED}),
    # -> paypal_order_created: the old PayPal order lapsed and a new one replaces it.
    # -> reconciliation_required: PayPal reports a change we didn't start (e.g. a webhook), so we check.
    S.AWAITING_BUYER_CHECKOUT: frozenset({
        S.CAPTURING, S.PAYPAL_ORDER_CREATED, S.AWAITING_APPROVAL, S.RECONCILIATION_REQUIRED, S.CANCELLED, S.EXPIRED, S.FAILED,
    }),
    # -> awaiting_buyer_checkout: PayPal declined the card or the buyer hasn't approved yet; they can try again.
    S.CAPTURING: frozenset({S.PAID, S.FAILED, S.RECONCILIATION_REQUIRED, S.AWAITING_BUYER_CHECKOUT}),
    S.RECONCILIATION_REQUIRED: frozenset({S.PAID, S.FAILED, S.AWAITING_BUYER_CHECKOUT, S.CAPTURING}),
    S.PAID: frozenset(),
    S.FAILED: frozenset(),
    S.CANCELLED: frozenset(),
    S.EXPIRED: frozenset(),
    S.REJECTED: frozenset(),
}
TERMINAL = frozenset(s for s, nxt in TRANSITIONS.items() if not nxt)


class InvalidTransition(Exception):
    def __init__(self, current: str, target: str):
        super().__init__(f"An order can't go from {current} to {target}.")
        self.current, self.target = current, target


def can_transition(current: str, target: str) -> bool:
    return OrderStatus(target) in TRANSITIONS[OrderStatus(current)]


def transition(order: Order, target: OrderStatus) -> None:
    if not can_transition(order.status, target):
        raise InvalidTransition(order.status, target)
    order.status = target.value


def claim(session: Session, order: Order, current: OrderStatus, target: OrderStatus) -> bool:
    """Atomic compare-and-set in the database: only one request can move the order out of `current`.
    Used before capture so two clicks (or a click plus a retry) can't both capture."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)
    res = session.execute(update(Order).where(Order.id == order.id, Order.status == current.value).values(status=target.value))
    session.commit()
    session.refresh(order)
    return res.rowcount == 1
