"""Webhook signature verification through PayPal's verify-webhook-signature API.

An event is trusted only when PayPal itself answers verification_status == "SUCCESS".
"""

import json
from collections.abc import Mapping

from app.integrations.paypal.client import PayPalClient

# Events we act on. Everything else is stored and ignored.
HANDLED_EVENTS = {
    "CHECKOUT.ORDER.APPROVED",
    "PAYMENT.CAPTURE.PENDING",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.DENIED",
    "CHECKOUT.PAYMENT-APPROVAL.REVERSED",
}

SIGNATURE_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}


def signature_fields(headers: Mapping[str, str]) -> dict[str, str] | None:
    """The five PayPal transmission headers, or None if any is missing."""
    lowered = {k.lower(): v for k, v in headers.items()}
    fields = {name: lowered.get(header, "") for name, header in SIGNATURE_HEADERS.items()}
    return fields if all(fields.values()) else None


def verify_signature(client: PayPalClient, fields: dict[str, str], webhook_id: str, raw_event: bytes) -> bool:
    # The raw body goes in unchanged: PayPal signed those exact bytes, and re-serialising can break the check.
    head = json.dumps({**fields, "webhook_id": webhook_id})[:-1]
    body = client.request(
        "POST", "/v1/notifications/verify-webhook-signature",
        content=head.encode() + b', "webhook_event": ' + raw_event + b"}",
    )
    return body.get("verification_status") == "SUCCESS"
