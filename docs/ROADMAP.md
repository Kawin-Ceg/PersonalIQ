# Build roadmap

One feature at a time. Each feature ships with a few focused tests (happy path plus the one failure that matters), not an exhaustive suite.

Guiding rule: PersonalIQ is done when the outcome is achieved, verified, or explicitly blocked on the user. Not when it has produced text.

| # | Status | Feature | Backend | Frontend | Tests |
|---|--------|---------|---------|----------|-------|
| 0 | done | Scaffold | FastAPI, config, health, Alembic | App shell, 6 screens, design tokens | health |
| 1 | done | Data model + demo catalog | 14 core tables, seed 44 products, 4 merchants, 2 demo users, GET /products | Discover screen lists catalog | seed is idempotent, prices are Decimal, money sent as string |
| 2 | done | Personal Intelligence Engine | Onboarding, memories with source + confidence, feedback, observed events, spending CSV import, GET /me/context | "You" screen: onboarding, what PersonalIQ knows, spending, feedback | feedback raises importance, CSV import, user correction wins |
| 3 | done | Deterministic services | Ranking score (weights from user context, hard exclusions), budget math, knapsack cart optimizer with shipping | Ranked catalog with score breakdown, Plan a cart | ranking explained, cart fits budget with shipping, budget math exact |
| 4 | done | Agent contracts + supervisor | AgentTask / AgentResult, five agents, LangGraph graph (Life + Buyer in parallel), rule-based intent reader, proposed order, SSE stream | Live Activity timeline, Home starts workflows | intent reader, end to end with LLM stubbed, blocked / needs input |
| 5 | done | Chat + intent parsing | POST /chat, Nemotron reads requests (validated by code, budgets from rules), follow-up questions, conversations | Home chat with quick answers, "understood" chips | clear request starts, question round trip, bad LLM output rejected |
| 6 | done | Approval boundary + risk policy | Approval bound to order hash + version, 24 h expiry, risk score per item (amount, past ratings, close calls, budget swaps, returns, new store, duplicates), keep / swap / remove, audit timeline | Approval Center with decision trail per item and order timeline | decisions required, change replaces approval, expiry, risk factors |
| 7 | done | PayPal Sandbox | Create order, capture, verify amount, idempotency, webhooks | PayPal checkout from approval | double capture is blocked |
| 8 | done | Post-purchase + receipt | Record payment, decision receipt, reminders, memory update | Purchases + Decision Receipt | receipt only after verified capture |
| 9 | partial | Finance view + learning loop (loop done) | Outcomes from receipts and feedback feed back into memories | Finance screen | a regret lowers that product's future score |

The Personal Intelligence Engine is built early (2), and its learning loop gets richer in 3 to 9.

Out of scope for the hackathon: calendar, live merchants, refunds, subscriptions, negotiation, portfolio data.

## How PersonalIQ learns (feature 2)

Four channels, all stored as memories with a `source` and `confidence`:

| Channel | Source | Confidence | Example |
|---------|--------|------------|---------|
| User-provided (onboarding, edits) | `user_stated` | 1.0 | "Durability matters most", "avoid leather" |
| Uploaded data (transaction CSV) | `uploaded` | 0.9 | Spending by category, top merchants |
| Feedback and outcomes | `feedback` | 0.8 | "Nonstick cookware 4/10, coating wore off" raises durability |
| Observed behaviour | `observed` | 0.6 | Rejected two recommendations as too expensive |

Rule: a `user_stated` memory is never overwritten by a lower-authority source. The user can inspect, correct or delete any memory; a correction becomes `user_stated`.
