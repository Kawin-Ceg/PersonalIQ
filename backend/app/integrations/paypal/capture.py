"""Capture an approved PayPal order. Idempotent through PayPal-Request-Id."""

from app.integrations.paypal.client import PayPalClient
from app.integrations.paypal.schemas import PayPalOrder


def capture_order(client: PayPalClient, paypal_order_id: str, request_id: str) -> tuple[PayPalOrder, dict]:
    """Raises PayPalTimeout when the outcome is unknown: the caller must reconcile, not assume failure."""
    body = client.request("POST", f"/v2/checkout/orders/{paypal_order_id}/capture", json={}, request_id=request_id)
    return PayPalOrder.model_validate(body), body
