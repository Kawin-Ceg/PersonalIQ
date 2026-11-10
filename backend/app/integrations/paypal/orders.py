"""Create and read PayPal orders (Orders v2)."""

from dataclasses import dataclass
from decimal import Decimal

from app.integrations.paypal.client import PayPalClient
from app.integrations.paypal.schemas import PayPalOrder


@dataclass(frozen=True)
class ChargeLine:
    name: str
    sku: str
    quantity: int
    unit_amount: Decimal


@dataclass(frozen=True)
class ChargeRequest:
    """Everything PayPal needs. Built by the payment service from the approved database order only."""

    reference_id: str  # our order id
    description: str
    currency: str
    item_total: Decimal
    shipping: Decimal
    tax: Decimal
    total: Decimal
    lines: tuple[ChargeLine, ...]


def _money(currency: str, value: Decimal) -> dict:
    return {"currency_code": currency, "value": f"{value:.2f}"}


def build_order_body(charge: ChargeRequest, brand_name: str = "PersonalIQ") -> dict:
    return {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": charge.reference_id,
            "custom_id": charge.reference_id,
            "description": charge.description[:127],
            "amount": {
                **_money(charge.currency, charge.total),
                "breakdown": {
                    "item_total": _money(charge.currency, charge.item_total),
                    "shipping": _money(charge.currency, charge.shipping),
                    "tax_total": _money(charge.currency, charge.tax),
                },
            },
            "items": [
                {
                    "name": line.name[:127], "sku": line.sku[:127], "quantity": str(line.quantity),
                    "unit_amount": _money(charge.currency, line.unit_amount), "category": "PHYSICAL_GOODS",
                }
                for line in charge.lines
            ],
        }],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "brand_name": brand_name,
                    "shipping_preference": "NO_SHIPPING",  # demo catalog: no real delivery
                    "user_action": "PAY_NOW",
                }
            }
        },
    }


def create_order(client: PayPalClient, charge: ChargeRequest, request_id: str) -> tuple[PayPalOrder, dict]:
    body = client.request("POST", "/v2/checkout/orders", json=build_order_body(charge), request_id=request_id)
    return PayPalOrder.model_validate(body), body


def get_order(client: PayPalClient, paypal_order_id: str) -> tuple[PayPalOrder, dict]:
    body = client.request("GET", f"/v2/checkout/orders/{paypal_order_id}")
    return PayPalOrder.model_validate(body), body
