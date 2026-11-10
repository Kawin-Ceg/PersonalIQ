# Agents

PersonalIQ is one system: a **Supervisor** and **five specialised agents**, sharing one **Personal Intelligence Engine**. The agents exchange typed contracts, not free text:

- **`AgentTask`:** `task_id, workflow_id, user_id, agent_name, objective, context, constraints, dependencies`
- **`AgentResult`:** `task_id, status, result, confidence, explanation, requires_human_approval, errors`

Every run is stored as an `agent_runs` row, which is what Activity streams and the decision receipt shows.

**The rule: agents decide, services compute, integrations execute.** Rankings, budgets, carts, risk, forecasts and payments are deterministic code (`app/services`). The language model is optional and does only three things: read a chat request into a structure (validated by code; budgets always come from rules), phrase the Supervisor's closing message, and phrase the Finance summary (shown only if every number in it matches a computed one). It never computes money, approves, or pays.

## The Supervisor (`app/agents/supervisor.py`, `app/orchestration/graph.py`)

A LangGraph state graph. The Supervisor plans, routes on results, recovers, and verifies.

```
plan ─(ok)→ Life Operations ┐ in parallel
     │      Consumer Buyer  ┘→ check research ─(ok)→ Procurement ─(ok)→ Financial ─(ok)→ verify
     │                               │                    │                  │
     └──────(needs input / failed)───┴────────────────────┴──(failed)→ recover
                                                                          ├─ fit_remaining → Procurement
                                                                          └─ deeper_search → Consumer Buyer (deep) → Procurement
```

- **Plan:** chooses the budget (from your request, else the matching saved budget, else the monthly one) and the order of work.
- **Route:** skips the remaining agents when planning or research fails or needs your input.
- **Recover**, decided from the failure itself, at most 2 times and each strategy once:
  - `fit_remaining`: the cart fit the planned amount, but earlier orders already used part of that saved budget, so it rebuilds for what's left.
  - `deeper_search`: the must-haves didn't fit, so the Consumer Buyer returns up to 12 options per item, cheaper ones included, and the cart is rebuilt.
- **Retry:** an agent that crashes is retried once. A reported failure is a real answer and isn't retried.
- **Bounds:** a 180 s time limit (checked between steps) and a 30-step cap.
- **Verify and policy gate:** before anything becomes an order, code checks that the total is within budget, every product came from the research, the currency is yours, and quantities are valid. Then it creates the order and asks for your approval. If nothing works, it says what it tried.

## 1. Life Operations (`app/agents/life_operations.py`)

Turns an objective into **needs** (must-have and nice-to-have) and a **task plan**:
- the purchase steps (owned by agents or by you)
- for a move: things PersonalIQ can't book (movers, utilities, address), marked as yours

Tasks have dependencies, and due dates worked backwards from your target date (assumed 7-day delivery plus a 2-day buffer, stated in the plan). It warns when the timeline is tight. Progress is tracked in `services/objectives.py`: automatic tasks tick only from real events (agents finishing, your approval, PayPal's verified capture, every item rated); you tick your own.

## 2. Consumer Buyer (`app/agents/consumer_buyer.py`)

Ranks the catalog for **you**, using `services/ranking.py`:

`score = wQ·quality + wV·value + wP·price + wR·durability + wF·fit`

- **Weights** come from your priorities, scaled by what matters to you. A poor aspect rating in a category gives that category its own weights.
- **Hard exclusions** are reported with reasons: a material you avoid, a store you avoid, a product you rated 5/10 or less, out of stock.
- **Your own aspect scores** replace the catalog's for products you've rated.
- **Search depth:** top 4 options per need, or 12 when the Supervisor asks for a deeper search.

## 3. Procurement (`app/agents/procurement.py`)

Builds the best cart within budget with a dynamic-programming knapsack (`services/cart.py`), including per-merchant shipping rules. Must-haves first; nice-to-haves are added if they fit, otherwise skipped with a reason. It never pays. It only prepares a proposal.

## 4. Financial Autopilot (`app/agents/financial.py`, `services/budget.py`, `services/finance.py`)

- **The cart check:** each order counts only against the budget it was planned with. Spent and committed (approved but unpaid) are separate. It also flags things you bought recently.
- **The Finance screen:**
  - monthly spending and categories
  - recurring payments (steady weekly or monthly, similar amount, seen 3+ times)
  - unusual payments (over 2× the category median)
  - a month-end forecast with its assumptions
  - "can I afford it?"
- **Income isn't known,** so no savings claims are made.

## 5. Post-Purchase (`app/agents/post_purchase.py`)

Runs once, only after PayPal confirms a capture. Records each item's return-by date (merchant return window) and warranty end (demo catalog), and asks for ratings. It never invents delivery, warranty or refund status. Ratings with aspects feed the learning loop (`services/learning.py`), and you see the before-and-after weights and ranks.

## Personal Intelligence Engine (`services/personal_intelligence.py`, `services/memory.py`)

| Channel | Source | Confidence |
|---|---|---|
| What you tell it (onboarding, corrections) | `user_stated` | 1.0 |
| Uploaded transactions | `uploaded` | 0.9 |
| Ratings and outcomes | `feedback` | 0.8 |
| Behaviour in the app | `observed` | 0.6 |

A memory can only be replaced by an equal or higher-authority source, so nothing overwrites what you said. You can inspect, correct (which makes it `user_stated`) or delete any memory under **You**.
