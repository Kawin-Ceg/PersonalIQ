"""PayPal Sandbox payments. Amounts are never accepted from the client; only ids."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.integrations.paypal.client import PayPalClient, get_paypal
from app.integrations.paypal.exceptions import PayPalConfigError
from app.models import User
from app.services import payment as svc
from app.services.settlement import SettlementError, charge_currency

router = APIRouter(prefix="/payments", tags=["payments"])


class _Strict(BaseModel):
    # Extra fields are refused, so a client can't slip in an amount or currency.
    model_config = ConfigDict(extra="forbid")


class CreateOrderIn(_Strict):
    order_id: uuid.UUID


class CaptureIn(_Strict):
    order_id: uuid.UUID
    paypal_order_id: str = Field(min_length=5, max_length=64, pattern=r"^[A-Z0-9]+$")


def paypal_client() -> PayPalClient:
    try:
        return get_paypal()
    except PayPalConfigError as e:
        raise HTTPException(503, {"code": "paypal_not_configured", "message": str(e)})


def _run(fn):
    try:
        return fn()
    except svc.PaymentError as e:
        raise HTTPException(e.status, {"code": e.code, "message": e.message, **e.extra})


@router.get("/paypal/config")
def config() -> dict:
    """What the browser needs to load the PayPal JS SDK. The client id is public; the secret never leaves the server."""
    s = get_settings()
    try:
        currency = charge_currency()
    except SettlementError:
        currency = None
    enabled = bool(s.paypal_client_id and s.paypal_client_secret and s.paypal_mode == "sandbox" and currency)
    return {"enabled": enabled, "client_id": s.paypal_client_id if enabled else None, "currency": currency,
            "mode": s.paypal_mode, "webhooks_configured": bool(s.paypal_webhook_id)}


@router.post("/paypal/create-order")
def create_order(data: CreateOrderIn, user: User = Depends(current_user), session: Session = Depends(get_session),
                 paypal: PayPalClient = Depends(paypal_client)) -> dict:
    return _run(lambda: svc.create_paypal_order(session, user, data.order_id, paypal))


@router.post("/paypal/capture-order")
def capture_order(data: CaptureIn, user: User = Depends(current_user), session: Session = Depends(get_session),
                  paypal: PayPalClient = Depends(paypal_client)) -> dict:
    return _run(lambda: svc.capture(session, user, data.order_id, data.paypal_order_id, paypal))


@router.post("/paypal/checkout-cancelled")
def checkout_cancelled(data: CaptureIn, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return _run(lambda: svc.checkout_cancelled(session, user, data.order_id, data.paypal_order_id))


@router.post("/paypal/webhook")
async def webhook(request: Request, session: Session = Depends(get_session), paypal: PayPalClient = Depends(paypal_client)) -> dict:
    raw = await request.body()
    return await run_in_threadpool(_run, lambda: svc.handle_webhook(session, paypal, raw, dict(request.headers)))


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return _run(lambda: svc.cancel_order(session, user, order_id))


@router.get("/{payment_id}")
def get_payment(payment_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return _run(lambda: svc.payment_for_user(session, user, payment_id))


@router.post("/{payment_id}/reconcile")
def reconcile(payment_id: uuid.UUID, user: User = Depends(current_user), session: Session = Depends(get_session),
              paypal: PayPalClient = Depends(paypal_client)) -> dict:
    return _run(lambda: svc.reconcile_for_user(session, user, payment_id, paypal))
