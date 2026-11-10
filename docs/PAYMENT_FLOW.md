# Payment flow (PayPal Sandbox)

PersonalIQ pays through **PayPal Orders v2** in the **Sandbox**. No real money moves. The backend refuses to start unless `PAYPAL_MODE=sandbox` and the base URL is the sandbox one.

## The rules

1. **The amount comes from the database, never from the browser.** The create and capture endpoints accept only ids; any extra field (such as `amount`) is rejected with 422.
2. **An approval covers one exact order version, including what PayPal will charge.** The approval fingerprint hashes items, prices, quantities, totals, the order currency, and the charge currency and amount.
3. **If anything changes after approval, the approval is void.** This covers items, quantities, totals that don't add up, or a catalog price that changed. The server invalidates it, reprices the order, bumps the version and asks the user to approve again (`409 reapproval_required`).
4. **Approved orders must be paid within 24 hours**, otherwise the order becomes `expired`.
5. **One capture per order.** The status is claimed atomically (`awaiting_buyer_checkout` → `capturing`) and the capture call carries a fixed `PayPal-Request-Id`, so PayPal also deduplicates retries.
6. **PAID only after verification.** PayPal's own response must show one `COMPLETED` capture. Its amount and currency must equal the approved charge, and it must carry our internal order id as `reference_id` / `custom_id`.
7. **A timeout is "unknown", not "failed".** The order moves to `reconciliation_required`, and the server asks PayPal (`GET /v2/checkout/orders/{id}`) what really happened before anything is retried.
8. **Nothing secret reaches the browser.** The JS SDK gets only the public client id, from `GET /payments/paypal/config`. Tokens and secrets are never logged. Stored PayPal responses have payer details removed.

## Currency

Orders are shown in the user's home currency (for example INR). The charge is made in `PAYPAL_CURRENCY`, which defaults to USD.

**Use US Sandbox accounts.** PayPal no longer processes domestic payments within India. Tested on 2026-11-10 with a Sandbox app from an India-registered developer account:

- INR order: create failed with `CURRENCY_NOT_SUPPORTED`.
- USD order paid by an India Sandbox buyer: checkout failed with `UNSUPPORTED_PAYEE_CURRENCY`.

The fix is to create, in developer.paypal.com → Testing Tools → Sandbox Accounts:

- a **Business** account with country **United States**
- a **Personal** account with country **United States**

Then create a REST app linked to that US business account, put its client id and secret in `backend/.env`, keep `PAYPAL_CURRENCY=USD`, and pay as the US personal account.

When the charge currency differs from the order currency, the charge is converted. Each line is converted at the **fixed demo rate** (`app/services/fx.py`), and the totals are rebuilt from the converted lines so that PayPal's own breakdown check is exact. The approval screen shows both amounts, for example "₹1,61,815.82, PayPal charges $1,914.98 USD".

## Order states

```
awaiting_approval -> approved -> paypal_order_created -> awaiting_buyer_checkout -> capturing -> paid
        |               |                                   |                          |
     rejected        expired                       cancelled / expired       failed / reconciliation_required
     expired         cancelled                     (buyer can retry)         (reconcile -> paid / failed / retry)
```

`app/services/order_state.py` holds the full transition table. Any move not in it raises `InvalidTransition`.

## Endpoints (`/api/v1/payments`)

| Method | Path | What it does |
|---|---|---|
| GET | `/paypal/config` | Public client id, charge currency, whether webhooks are configured |
| POST | `/paypal/create-order` | `{order_id}` → creates (or reuses) the PayPal order for the approved order |
| POST | `/paypal/capture-order` | `{order_id, paypal_order_id}` → captures, verifies, returns the payment |
| POST | `/paypal/checkout-cancelled` | The buyer closed PayPal. Recorded; nothing changes |
| POST | `/orders/{order_id}/cancel` | The user calls off an approved, unpaid order |
| GET | `/{payment_id}` | Payment status |
| POST | `/{payment_id}/reconcile` | Ask PayPal what happened and record exactly that |
| POST | `/paypal/webhook` | PayPal webhooks (signature-verified, deduplicated) |

## Webhooks

Handled: `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, `CHECKOUT.PAYMENT-APPROVAL.REVERSED`.

- Each event is verified with PayPal's `verify-webhook-signature` API using `PAYPAL_WEBHOOK_ID`. The raw body is forwarded byte for byte. An unverified event is rejected with 400 and not stored.
- The event id is stored once (unique), so a repeat delivery returns `duplicate` and does nothing.
- For capture events the payload's amounts are not trusted. The server fetches the order from PayPal and runs the same verification as a normal capture.
- Without `PAYPAL_WEBHOOK_ID` the endpoint answers 503. Payments still work, because capture is confirmed synchronously.

**PayPal can't reach `localhost`.** To receive webhooks locally, expose the backend through a tunnel:

```
ngrok http 8000                       # or: cloudflared tunnel --url http://localhost:8000
```

Then in developer.paypal.com → Apps & Credentials → your app → Webhooks, add `https://<tunnel-host>/api/v1/payments/paypal/webhook`, select the five events above, and copy the webhook id into `PAYPAL_WEBHOOK_ID` in `backend/.env`. Restart the backend.

## Try it with the Sandbox

1. In `backend/.env`, set `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` from your Sandbox app.
2. Run `alembic upgrade head`, start the backend and the frontend.
3. From Home, ask for something, open the approval, decide the flagged items and click **Approve**.
4. The **Payment** section shows the PayPal button. Log in with your **Sandbox personal (buyer) account** (developer.paypal.com → Testing Tools → Sandbox Accounts).
5. After you approve in PayPal, the backend captures and verifies the payment. The page shows **Paid, verified with PayPal** with the PayPal order id and capture id. You can check the same ids in the Sandbox business account's activity.

## Tests

`backend/tests/test_payments.py` runs the real client code against a fake PayPal (`httpx.MockTransport`). It covers:

- the happy path, and a second capture being blocked
- buyer cancel
- unapproved, unknown and other users' orders
- a client-sent amount being rejected
- an order changed after approval
- a timeout before and after PayPal captured
- a capture for the wrong amount
- webhook signature failure and duplicate delivery
- bad credentials and token caching
- the state machine

These are not live PayPal tests. Live Sandbox behaviour is checked by hand (see `docs/IMPLEMENTATION_STATUS.md`).
