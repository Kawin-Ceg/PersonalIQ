# Architecture

```
Next.js UI ──HTTP / SSE──> FastAPI (/api/v1)
                             │
                             ├─ app/orchestration   LangGraph: Supervisor routing, recovery, retries, limits
                             ├─ app/agents          Supervisor + Life Operations, Consumer Buyer, Procurement,
                             │                      Financial Autopilot, Post-Purchase (typed AgentTask / AgentResult)
                             ├─ app/services        deterministic logic: ranking, cart optimiser, budgets, finance,
                             │                      approval boundary, risk policy, order state machine, payments,
                             │                      receipts, objectives, learning, personal intelligence
                             ├─ app/integrations    PayPal REST: OAuth, Orders v2, capture, webhook verification
                             └─ PostgreSQL          source of truth (SQLAlchemy 2, Alembic migrations)
```

## Rules we don't break

1. **Agents decide, services compute, integrations execute.** Agents never touch payment credentials. The language model never does arithmetic, approves, or pays.
2. **Money is `Decimal` / `NUMERIC(18,2)` with an ISO 4217 currency.** No floats anywhere in money paths.
3. **An approval is bound to one exact order version.** A SHA-256 fingerprint of items, prices, quantities, totals, currency and the PayPal charge. Any change voids it, and a new approval is needed.
4. **The amount to charge comes from the database.** Payment endpoints accept ids only.
5. **Capture is server-side and idempotent.** An atomic status claim, plus `PayPal-Request-Id`. The response is verified (amount, currency, order reference) before an order is marked paid.
6. **A capture timeout is "unknown", not "failed".** Reconcile with PayPal before doing anything else.
7. **Every order status change goes through the state machine** (`services/order_state.py`). Illegal moves raise.
8. **Done means verified.** Automatic tasks, receipts and "Paid" labels come only from real events.

## Data model (main tables)

| Area | Tables |
|---|---|
| People | `users`, `budgets`, `memories`, `transactions`, `feedback` (with `aspects`), `user_events`, `conversations`, `messages` |
| Catalog | `merchants`, `products` (seeded demo data) |
| Work | `objectives`, `tasks`, `workflows` (graph state and outcome), `agent_runs` |
| Commerce | `orders` (`budget_id`, version), `order_items`, `approvals` (fingerprint, risk, charge), `payments` (PayPal ids, request id, attempt, verification), `payment_events` (PayPal responses and webhooks, unique ids), `audit_logs` |

Migrations live in `backend/alembic/versions`.

## Order lifecycle

```
awaiting_approval → approved → paypal_order_created → awaiting_buyer_checkout → capturing → paid
       ↘ rejected / expired     ↘ cancelled / expired                            ↘ failed / reconciliation_required
```

The details are in [PAYMENT_FLOW.md](PAYMENT_FLOW.md).

## Frontend

Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 4, Phosphor icons. The screens are Home (chat and objectives), Activity (live agent timeline), Discover, Approvals (with PayPal checkout), Purchases and receipts, Finance, Objectives, and You (memories, spending, ratings). One column, pop-ups for detail, and money always in the user's own currency.

## Honesty in the demo

- The catalog, ratings and warranties are a labelled demo catalog, not live inventory.
- Exchange rates are fixed demo rates.
- PayPal runs in the Sandbox. "Paid" appears only after a verified Sandbox capture.
- Delivery tracking doesn't exist for the demo catalog, so it's shown as unknown. Tasks PersonalIQ can't book are listed as yours.
