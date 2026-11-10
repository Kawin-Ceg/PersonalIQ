# API

Base URL: `http://localhost:8000/api/v1`. Interactive docs, with every request and response schema, are at **http://localhost:8000/docs**.

## Conventions

- **Current user.** There's no login in this build. The frontend sends the selected demo user's id in the `X-PersonalIQ-User` header (or as `?user=` for Server-Sent Events). Without it, the first demo user is used. Every resource is checked against that user, and someone else's resource answers 404.
- **Money** is a decimal **string** (`"161815.82"`) with an ISO 4217 `currency`. Never a float.
- **Errors** use FastAPI's shape. For business refusals, `detail` is `{"code": "...", "message": "..."}`, for example `409 {"code": "reapproval_required", ...}`.
- **Amounts are never accepted from the client for payments.** Payment requests take ids only, and extra fields are rejected with 422.

## Endpoints

### System
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API, database, PayPal and LLM configuration status |

### Personal Intelligence
| Method | Path | Purpose |
|---|---|---|
| GET | `/users` | Demo users (for the switcher) |
| GET | `/me/context` | Everything PersonalIQ uses about you: importance weights, category weights, exclusions, spending |
| POST | `/me/onboarding` | Priorities, price sensitivity, materials and stores to avoid, likes, monthly budget |
| GET | `/me/memories` | Memories with `source` and `confidence` |
| PATCH | `/me/memories/{id}` | Correct a memory (it becomes `user_stated`) |
| DELETE | `/me/memories/{id}` | Forget a memory |
| GET / POST | `/me/feedback` | Ratings. POST with `order_id`, `product_id`, `rating`, optional `aspects` (`quality`, `durability`, `value`, each 1-10). The response's `learning` shows weights and ranks before and after |
| POST | `/me/events` | Observed behaviour (views, comparisons, accepted or rejected recommendations) |
| POST | `/me/transactions/import` | Upload a transactions CSV: `date,merchant,category,amount[,currency]` |

### Catalog
| Method | Path | Purpose |
|---|---|---|
| GET | `/products` | Demo catalog |
| GET | `/products/ranked` | Ranked for you, with the score breakdown and what was excluded (and why). Filters: `category`, `need`, `max_price` |
| GET | `/products/needs` | Needs (bed frame, kettle, …) with counts |
| POST | `/cart/optimize` | Best cart for a budget and a list of needs |

### Requests, agents and objectives
| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Talk to PersonalIQ. Starts a workflow, or asks a follow-up question |
| GET | `/chat/{conversation_id}/messages` | Conversation history |
| POST | `/workflows` | Start a workflow from a message directly |
| GET | `/workflows`, `/workflows/{id}` | Workflows with every agent run, result and supervisor decision |
| GET | `/workflows/{id}/events` | Server-Sent Events: `update` whenever an agent starts or finishes, then `done` |
| GET | `/objectives`, `/objectives/{id}` | Objectives with their task plan, dependencies, due dates and progress |
| POST | `/objectives/{id}/tasks/{task_id}` | `{"done": true}`. Only for your own (manual) tasks, and only once their dependencies are done |

### Approvals
| Method | Path | Purpose |
|---|---|---|
| GET | `/approvals`, `/approvals/count` | Approvals waiting for you |
| GET | `/approvals/{id}` | The exact order, per-item risk, decision trail, budget, charge, payment state, timeline |
| POST | `/approvals/{id}/items/{item_id}` | `keep`, `remove` or `swap` (`product_id`). A change creates a new order version and a new approval |
| POST | `/approvals/{id}/approve` | `{"order_hash": "<the version you looked at>"}` |
| POST | `/approvals/{id}/reject` | Optional `reason` (`too_expensive`, `wrong_items`, `not_now`, `other`) |

### Payments (PayPal Sandbox)
| Method | Path | Purpose |
|---|---|---|
| GET | `/payments/paypal/config` | Public client id and charge currency for the JS SDK |
| POST | `/payments/paypal/create-order` | `{"order_id"}` → PayPal order id. The amount comes from the approved database order |
| POST | `/payments/paypal/capture-order` | `{"order_id", "paypal_order_id"}` → capture, verify, record. Calling it again returns `already_captured` without a second capture |
| POST | `/payments/paypal/checkout-cancelled` | The buyer closed PayPal. Recorded; nothing changes |
| POST | `/payments/orders/{order_id}/cancel` | Call off an approved, unpaid order |
| GET | `/payments/{id}` | Payment state |
| POST | `/payments/{id}/reconcile` | Ask PayPal what happened (after a timeout or pending capture) |
| POST | `/payments/paypal/webhook` | Signed PayPal webhooks (verified with PayPal, deduplicated) |

### Purchases, receipts and finance
| Method | Path | Purpose |
|---|---|---|
| GET | `/orders` | Orders past the proposal stage, with what the receipt may claim (`paid` only when verified) |
| GET | `/orders/{id}/receipt` | The decision receipt |
| GET | `/finance/overview` | Monthly spending, categories, recurring and unusual payments, forecast with assumptions, budgets |
| GET | `/finance/summary` | A short written summary. Shown only if every number in it matches a computed figure |
| POST | `/finance/affordability` | `{"amount", "budget_name"?}` → `fits`, `tight` or `over`, with reasons |

## Example: pay for an approved order

```bash
U=<demo user id from GET /users>
curl -X POST localhost:8000/api/v1/payments/paypal/create-order \
     -H "X-PersonalIQ-User: $U" -H "Content-Type: application/json" -d '{"order_id": "<order id>"}'
# -> {"paypal_order_id": "5O190127TN364715T", "amount": "1914.98", "currency": "USD", "order_status": "awaiting_buyer_checkout"}
# The buyer approves in the PayPal window (JS SDK), then:
curl -X POST localhost:8000/api/v1/payments/paypal/capture-order \
     -H "X-PersonalIQ-User: $U" -H "Content-Type: application/json" \
     -d '{"order_id": "<order id>", "paypal_order_id": "5O190127TN364715T"}'
# -> {"order_status": "paid", "verified": true, "capture_id": "...", ...}
```
