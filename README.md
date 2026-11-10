# PersonalIQ

**Intelligence that understands you.**

PersonalIQ learns how you spend, choose and decide, then coordinates five AI agents to plan a purchase, check it against your money, and buy it through PayPal once you approve. Built for the PayPal AI Hackathon 2026.

> Say *"Set up my new apartment by 10 December"*. PersonalIQ works out what you need, ranks products by what matters to *you*, builds the best cart within your budget, checks it against your saved budgets, and asks for your approval of that exact order. You pay with PayPal, it verifies the capture, writes a decision receipt, and asks later how things worked out. A bad experience changes what it picks next time.

## What's real and what's demo

| Real | Demo |
|---|---|
| PayPal **Sandbox** payments: Orders v2 create, capture, verification, idempotency, reconciliation, signed webhooks | The product catalog (44 items, 4 merchants) is **seeded demo data**, not live inventory |
| Personal memory with source and confidence; learning from your ratings | Exchange rates are **fixed demo rates** |
| Deterministic money math (Decimal), budgets, ranking, cart optimiser | Two demo users (Priya, INR; Theo, SEK) with seeded history |
| LangGraph supervisor with recovery, retries and a policy gate | No real delivery tracking or external bookings (they're shown as unknown or as your own tasks) |

No payment is ever simulated. An order is **Paid** only after PayPal's own capture response confirms the approved amount, currency and order.

## How it works

```
You ──> Supervisor (LangGraph) ──> Life Operations ┐ in parallel
             │                     Consumer Buyer  ┘
             │                     Procurement ──> Financial Autopilot
             │   recovers when a cart or budget check fails (bounded)
             ├─> policy gate ──> proposed order ──> YOU APPROVE (exact version) ──> PayPal ──> verified capture
             └─> Post-Purchase: receipt, return dates, "how did it go?" ──> Personal Intelligence learns
```

- **Agents decide, services compute, integrations execute.** No language model does money math, approves anything, or touches PayPal.
- **An approval covers one exact order version**, including what PayPal will charge. Any change voids it.
- **Personal Intelligence** combines what you tell it, the transactions you upload, what you do in the app, and your ratings. Each fact records its source and confidence, and you can correct or delete it.

More detail: [Agents](docs/AGENTS.md) · [Architecture](docs/ARCHITECTURE.md) · [Payment flow](docs/PAYMENT_FLOW.md) · [API](docs/API.md)

## Run it locally

You need Python 3.12, Node 20+, PostgreSQL 15+, and PayPal Sandbox credentials. Full steps for Windows and macOS/Linux are in **[docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)**. In short:

```bash
# 1. Config: copy .env.example to backend/.env, set DATABASE_URL and the PayPal Sandbox keys
# 2. Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate     # Windows: py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.seed.run                                     # demo catalog + 2 demo users
uvicorn app.main:app --port 8000
# 3. Frontend (second terminal)
cd frontend && npm install && npm run dev                   # http://localhost:3000
```

Before a demo, `python -m app.seed.reset --yes` wipes the local data and seeds a fresh demo. Without `--yes` it only shows what it would delete.

## A two-minute demo

1. **Home**: ask *"Set up my new apartment with the essentials"*. Watch the agents in **Activity**.
2. **Approvals**: decide the flagged items (keep, swap or remove), then approve the exact order.
3. **Payment**: pay with the PayPal button using a US Sandbox personal account. The page shows *Paid, verified with PayPal* with the capture ID.
4. **Purchases**: open the **decision receipt**: your request, every agent's step, the alternatives each pick beat, the budget check, the PayPal IDs.
5. Rate the bed frame's **durability: Poor**. PersonalIQ shows how Furniture scoring and the ranking changed.
6. **Finance**: spending, budgets, recurring payments, and *"Can I afford it?"*. **Objectives** on Home: the task plan.
7. Ask for the apartment again: the budget is mostly used, so the Supervisor tries to recover, then explains why it stops.

## Tech

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · LangGraph · Pydantic · PayPal REST (Orders v2) and JS SDK · Next.js 15 · React 19 · TypeScript · Tailwind CSS 4. The language model is any OpenAI-compatible endpoint (tested with NVIDIA Nemotron via NVIDIA and OpenRouter) and is optional.

```
backend/   app/agents (supervisor + 5 agents) · app/orchestration (LangGraph) · app/services (deterministic logic)
           app/integrations/paypal · app/models · alembic/ · tests/
frontend/  app/ (screens) · components/ · lib/ · types/
docs/      setup, architecture, agents, payments, API, status
```

## Tests

```bash
cd backend && pytest          # 41 tests; PayPal is faked at the HTTP level, so no network is needed
cd frontend && npx tsc --noEmit && npm run lint
```

Live Sandbox behaviour was checked by hand. See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## Limitations

There's no login: you pick a demo user in the sidebar. There's no investment portfolio analysis, and refunds aren't supported. Live webhooks need a public tunnel and haven't been verified end to end. Details are in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## License

[MIT](LICENSE)
