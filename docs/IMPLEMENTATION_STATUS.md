# Implementation status

Last audit: 2026-11-10. The codebase was built under the working name **Morrow** and has been renamed to **PersonalIQ** throughout.

How to read this: **Done** means implemented and covered by a passing test. **Partial** means some of it exists. **Missing** means nothing beyond a placeholder.

## Verified during the audit

| Check | Result |
|---|---|
| Backend tests (`pytest`) | 20 passed |
| Database migrations | Postgres at head (`23eeef96301d`), 6 migrations |
| Seed data | 2 demo users (INR, SEK), 4 merchants, 44 demo products, 9 memories, 20 uploaded transactions |
| Frontend type-check (`tsc --noEmit`) | Clean |
| Frontend lint (`eslint`) | Clean |
| PayPal Sandbox OAuth (client credentials) | HTTP 200, token issued. Credentials in `backend/.env` are valid |
| PayPal order create / capture / webhook | Implemented in Feature 1 (see below) |

## Feature 1 verification (2026-11-10)

| Check | Result |
|---|---|
| Backend tests | 27 passed (7 new in `test_payments.py`, against a fake PayPal at the HTTP level) |
| Mutation check | Disabling capture verification makes `test_capture_for_the_wrong_amount_is_not_paid` fail |
| Migration `5c0846941ffa` | Applied to Postgres |
| Live Sandbox: OAuth, create order, idempotent create (same request id returns same order), get order | Works |
| Live Sandbox: capture before buyer approval | PayPal 422 `ORDER_NOT_APPROVED`, mapped to `buyer_action_required`; order stays payable |
| Live Sandbox: wrong client secret | Clean `paypal_auth` error, nothing sent |
| Live Sandbox: full API run (workflow, approve, create-order) | ₹1,61,815.82 order became a $1,914.98 USD PayPal order |
| Live Sandbox: buyer login + capture in the browser | **Verified.** US Sandbox buyer paid with a test Visa. PayPal order `07V981413V019334R`, capture `8M704514CF839931K` COMPLETED for $1,914.98 USD. Confirmed in the database and by a separate GET to PayPal (amount, currency, order reference). 4 ledger rows add up to the order total ₹1,61,815.82 |
| Sandbox account country | India-registered Sandbox accounts fail (INR: `CURRENCY_NOT_SUPPORTED`; USD to an India merchant: `UNSUPPORTED_PAYEE_CURRENCY`). Use US business + personal Sandbox accounts |
| Live webhooks | **Not verified.** `PAYPAL_WEBHOOK_ID` is empty and no tunnel is set up |
| Frontend `tsc`, `eslint`, `next build` | Clean |

## Feature map (master instruction numbering)

| # | Feature | Status | What exists | Gaps |
|---|---|---|---|---|
| 0 | Repository audit | Done | This file | |
| 1 | PayPal Sandbox payments | Done, verified live in Sandbox | `integrations/paypal/` (auth with token cache, client, orders, capture, webhooks, schemas, exceptions), `services/order_state.py` (state machine), `services/settlement.py` (USD charge from the DB order), `services/payment.py` (create, capture, verify, reconcile, webhooks), `api/routes/payments.py`, PayPal checkout on the approval page. See `docs/PAYMENT_FLOW.md` | Live webhooks not yet verified (need a tunnel + `PAYPAL_WEBHOOK_ID`). Refunds out of scope |
| 2 | Personal Intelligence Engine | Done (mostly) | `services/personal_intelligence.py`, `services/memory.py`: onboarding, memories with source + confidence, feedback raises importance, observed events, CSV spending import, `GET /me/context`, user correction wins. "You" screen | Memories have no explicit `confirmed` flag (source `user_stated` plays that role). Feedback is one rating + reasons, not per-attribute scores (battery 4/10, performance 9/10). Code lives in one service, not the `personal_intelligence/` package the spec lists (kept as is, not worth a rewrite) |
| 3 | Consumer Buyer Agent | Done | `services/ranking.py` deterministic score with weights from user context, hard exclusions, explained breakdown. Discover screen with search, filters, product dialog | No side-by-side compare endpoint |
| 4 | Financial Autopilot | Done (no portfolio) | `services/finance.py` + `/finance/overview`, `/finance/affordability`, `/finance/summary`; Finance screen. Monthly everyday spending, categories with 30-day change, recurring detection (steady weekly/monthly, similar amount, 3+ times), unusual payments (>2x category median), month-end forecast with stated assumptions, budgets (spent vs committed), "can I afford it". Orders now carry `budget_id` and count only against their own budget; payment-in-progress states count as committed (both were bugs). Optional LLM summary is accepted only if every number in it is one of the computed ones (rounding allowed), else a fixed fallback | Investment portfolio analysis not built (no portfolio data; out of scope in the original roadmap). Income unknown, so no savings claims. Savings goals not built |
| 5 | Procurement Agent | Done | `services/cart.py` budget-constrained knapsack with shipping, `agents/procurement.py` creates the proposed order | Tax is always 0 (demo catalog has no tax data) |
| 6 | Human approval and trust | Done | `services/approval.py`: hash + version binding, supersede on change, expiry, per-item risk policy, keep/swap/remove, reject with reason, audit timeline. Approval Center UI | No explicit "cancel after approval" action |
| 7 | Life Operations Agent | Done | `agents/life_operations.py` builds a task plan per template: the purchase pipeline (owned by agents or you) plus life tasks PersonalIQ can't book (movers, utilities, address), marked external. Dependencies, and due dates worked backwards from the target date (assumed 7-day delivery + 2-day buffer, stated), with a tight-timeline warning. `tasks` table (migration `aff205808dc8`), `services/objectives.py`: auto tasks ticked only from real events (agent runs, approval, verified PayPal capture, all items rated), manual tasks ticked by the user, a task can't be ticked before its dependencies. `/objectives` API and objective page linked from Home and Activity. Requests understand "by 15 December" | Only the apartment template has life tasks; other templates get the purchase pipeline. No reminders or notifications. Nothing is booked externally |
| 8 | Post-Purchase Agent | Done | `agents/post_purchase.py`: runs once, only after a verified capture (called from the payment service). Records return-by dates (merchant return window), warranty end (demo catalog) and a feedback request per item; logged as an agent run. Feedback can be tied to a purchased item (`order_id`): own, paid order, item in it, once per item; low ratings become lessons and raise importance | Delivery tracking doesn't exist for the demo catalog (shown as unknown, never guessed) |
| 9 | Supervisor + LangGraph | Done | `orchestration/graph.py`: conditional routing after plan, research, cart and budget check. Recovery decided from results (`supervisor.decide_recovery`): `fit_remaining` (a saved budget partly used by earlier orders: rebuild for what's left) and `deeper_search` (Consumer Buyer returns up to 12 options per item, cheaper ones included). At most 2 recoveries, each strategy once; every decision is recorded as a `supervisor_recover` agent run shown in Activity and the receipt. A crashed agent is retried once (reported failures aren't). Time limit 180 s and step limit 30. Deterministic policy gate before any order (total within budget, products from the research, user's currency, quantities). Verified live: with ₹7,184 left, it tried both recoveries, then stopped and said so | `checkpoints.py` / `planner.py` are still stubs: state is kept in `workflows.state`, not a LangGraph checkpointer. The approval pause happens outside the graph (the workflow ends at 'awaiting approval') |
| 10 | Decision Receipt | Done | `services/receipt.py`, `GET /orders`, `GET /orders/{id}/receipt`, Purchases screen and receipt page. Built from stored records (agent snapshots, approval, audit, payment), not recomputed. States: proposed, approved, payment pending, paid, payment failed, not bought. "Paid" needs both a paid order and a verified payment | |
| 11 | UX / dashboard | Partial | Shell + Home (chat), Activity, Discover, You, Approvals. Design tokens, dialog/tooltip primitives | Purchases and Finance are empty states. No receipt screen |
| 12 | End-to-end test | **Missing** | Workflow test with LLM stubbed | Full journey through PayPal capture |

## Cross-cutting gaps and risks

1. **No authentication.** The current user comes from an `X-PersonalIQ-User` header (demo user switcher). Payment endpoints will check ownership against that user, which is fine for a local demo but is not real auth. Recommendation: keep it for the hackathon and say so in the docs; add login only if time allows.
2. **Currency vs PayPal.** Decided: orders show in the home currency, and PayPal charges in USD (`PAYPAL_CURRENCY`) at the fixed demo rate. Both amounts are covered by the approval.
3. **LLM provider.** Uses an OpenAI-compatible client (currently Nemotron through OpenRouter). Groq, Ollama and Gemini all expose OpenAI-compatible endpoints, so they work by changing `LLM_BASE_URL` / `LLM_MODEL` / key. `.env.example` should document this.
4. **pgvector** is not used. Memories are structured rows, retrieved by type. Adding embeddings is optional.
5. **Icons** use Phosphor, not Lucide. Kept (already consistent across the app).
6. **Repository.** The root folder is not a git repo, while `frontend/` has its own `.git` from create-next-app. Before publishing, remove `frontend/.git` and init one repo at the root, or the frontend will not upload correctly.
7. **Docs** missing: LICENSE, `docs/PAYMENT_FLOW.md`, `docs/AGENTS.md`, `docs/API.md`, `docs/LOCAL_SETUP.md`.

## Existing bugs

None found: all tests pass, type-check and lint are clean. No manual bug hunt was done beyond that.

## Recommended sequence

1. ~~PayPal Sandbox payments (Feature 1)~~ done.
2. ~~Post-Purchase + Decision Receipt (8, 10)~~ done.
3. ~~Learning loop + per-attribute feedback (2.5, 8)~~ done: aspect ratings (quality, durability, value for money) on purchases. A poor aspect (Poor or Weak) becomes a category memory (source feedback, 80% confidence) that gives that category its own ranking weights (4x for a lesson from experience vs 2.5x for a general "high"). Your aspect score replaces the catalog's quality/durability score for that exact product. After saving, the UI shows weights and ranks before and after (`services/learning.py`). Users can lower or delete the memory and the weights follow. Live dry run on the demo data: bed frame durability poor took Furniture durability from 30% to 40% and swapped the top two bed frames.
4. ~~Finance screen (4)~~ done.
5. ~~Life Operations tasks (7)~~ done.
6. ~~Rename to PersonalIQ, docs~~ done. Remaining: repo cleanup (single git repo) and an end-to-end run (12).

## Housekeeping

- Done: renamed Morrow to PersonalIQ (UI, header `X-PersonalIQ-User`, demo emails `@demo.personaliq.app`, docs).
- Done: `python -m app.seed.reset --yes` resets the demo; README, LOCAL_SETUP, API, AGENTS, ARCHITECTURE and LICENSE are written.
- Not done: one git repo at the root (frontend/ still has its own .git from create-next-app).
