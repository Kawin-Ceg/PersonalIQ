"""Typed views of the PayPal Orders v2 responses we rely on. Unknown fields are ignored."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PayPalMoney(_Lenient):
    currency_code: str
    value: Decimal


class CaptureStatusDetails(_Lenient):
    reason: str | None = None


class PayPalCapture(_Lenient):
    id: str
    status: str  # COMPLETED | PENDING | DECLINED | FAILED | PARTIALLY_REFUNDED | REFUNDED
    amount: PayPalMoney | None = None
    custom_id: str | None = None
    status_details: CaptureStatusDetails | None = None
    final_capture: bool | None = None


class PayPalPayments(_Lenient):
    captures: list[PayPalCapture] = Field(default_factory=list)


class PayPalPurchaseUnit(_Lenient):
    reference_id: str | None = None
    custom_id: str | None = None
    amount: PayPalMoney | None = None
    payments: PayPalPayments | None = None


class PayPalOrder(_Lenient):
    id: str
    # CREATED | SAVED | APPROVED | VOIDED | COMPLETED | PAYER_ACTION_REQUIRED
    status: str
    purchase_units: list[PayPalPurchaseUnit] = Field(default_factory=list)

    def captures(self) -> list[PayPalCapture]:
        return [c for pu in self.purchase_units if pu.payments for c in pu.payments.captures]


class WebhookEvent(_Lenient):
    id: str
    event_type: str
    resource_type: str | None = None
    resource: dict = Field(default_factory=dict)

    def paypal_order_id(self) -> str | None:
        """Checkout events carry the order; capture events point to it in supplementary_data."""
        if self.event_type.startswith("CHECKOUT."):
            return self.resource.get("id")
        related = (self.resource.get("supplementary_data") or {}).get("related_ids") or {}
        return related.get("order_id")


def strip_personal_data(body: dict) -> dict:
    """Drop payer details before storing a PayPal response: we only keep what proves the payment."""
    return {k: v for k, v in body.items() if k not in ("payer", "payment_source", "links")}
