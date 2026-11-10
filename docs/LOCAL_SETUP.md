# Local setup

PersonalIQ runs entirely on your machine: a FastAPI backend, a Next.js frontend and a local PostgreSQL. Payments go to the **PayPal Sandbox** with your own Sandbox credentials. No real money moves.

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | **3.12** | 3.13/3.14 may lack wheels for some dependencies |
| Node.js | 20 or newer | includes npm |
| PostgreSQL | 15 or newer | local install or Docker |
| PayPal Developer account | free | developer.paypal.com |

## 2. PayPal Sandbox (5 minutes)

1. Log in at **developer.paypal.com** → **Testing Tools → Sandbox Accounts → Create account**:
   - one **Business** account, country **United States**
   - one **Personal** account, country **United States** (this is your buyer; it comes with a test balance and card)
2. **Apps & Credentials** → **Sandbox** tab → **Create App**. Choose **Merchant** and link it to the **US Business** account.
3. Copy the app's **Client ID** and **Secret**.

> Use US accounts. With India-registered Sandbox accounts, PayPal rejects these payments (`CURRENCY_NOT_SUPPORTED` for INR, `UNSUPPORTED_PAYEE_CURRENCY` for USD), because PayPal doesn't process domestic payments within India. See [PAYMENT_FLOW.md](PAYMENT_FLOW.md).

## 3. Database

Create an empty database named `personaliq`:

```bash
# macOS / Linux
createdb -U postgres personaliq
```

```powershell
# Windows PowerShell (adjust the path to your PostgreSQL version)
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres personaliq
```

Or with Docker: `docker run -d --name personaliq-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=personaliq -p 5432:5432 postgres:16`

## 4. Configure

Copy the example file and fill it in:

```bash
cp .env.example backend/.env                 # macOS / Linux
```

```powershell
Copy-Item .env.example backend\.env          # Windows PowerShell
```

In `backend/.env`, set at least:

- `DATABASE_URL`, for example `postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/personaliq`
- `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` from step 2 (leave `PAYPAL_CURRENCY=USD`)
- optional: an LLM key (`LLM_API_KEY` or `OPENROUTER_API_KEY`). Without one, PersonalIQ uses its built-in rules.

For the frontend, create `frontend/.env.local` with one line:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## 5. Backend

```bash
# macOS / Linux
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed.run
uvicorn app.main:app --port 8000
```

```powershell
# Windows PowerShell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.seed.run
uvicorn app.main:app --port 8000
```

Check it: http://localhost:8000/api/v1/health should show `"database": "ok"` and `"paypal_configured": true`. Interactive API docs are at http://localhost:8000/docs.

## 6. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. The sidebar footer shows whether the API and database are reachable. The user switcher at the bottom of the sidebar picks a demo user: **Priya** (INR, with history) or **Theo** (SEK, new, good for trying onboarding).

## 7. Try a payment

1. On Home, ask *"Set up my new apartment with the essentials"*.
2. Open the approval, decide the flagged items, and click **Approve**.
3. In **Payment**, click the PayPal button and log in with your **US Sandbox personal** account. Pick the **Visa**: a bank payment can come back as *pending* for days, and PersonalIQ won't call that paid.
4. You'll see **Paid, verified with PayPal** with the PayPal order and capture IDs. The same IDs appear in the Sandbox business account's activity.

## Reset the demo

```bash
python -m app.seed.reset          # shows what would be deleted, changes nothing
python -m app.seed.reset --yes    # deletes all local PersonalIQ data and seeds a fresh demo
```

Run it from `backend/` with the virtual environment active. Payments already made in the PayPal Sandbox stay there; only the local records are removed.

## Tests

```bash
cd backend && pytest                                  # PayPal is faked at the HTTP level: no network needed
cd frontend && npx tsc --noEmit && npm run lint
```

## Webhooks (optional)

PayPal can't reach `localhost`. To receive webhooks, run a tunnel (`ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`), register `https://<tunnel>/api/v1/payments/paypal/webhook` on your Sandbox app, and put its id in `PAYPAL_WEBHOOK_ID`. Payments work without webhooks, because each capture is confirmed directly with PayPal. Details are in [PAYMENT_FLOW.md](PAYMENT_FLOW.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pip install` fails building wheels | Use Python 3.12 |
| Health shows `database: unreachable` | Check `DATABASE_URL`, and that PostgreSQL is running and the database exists |
| PayPal window: "Things don't appear to be working" | Your Sandbox accounts are probably India-registered. Use US accounts (step 2) |
| "PayPal isn't configured on the server" | Set `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` in `backend/.env` and restart the backend |
| Payment shows "Checking the payment with PayPal" | The capture is pending or uncertain. Click **Check with PayPal**; it never assumes success |
| Asking for the apartment again is blocked | The Apartment move budget is already used by the earlier order. That's correct; run the reset for a fresh demo |
| Browser shows CORS errors | `FRONTEND_ORIGIN` must match the URL you open (default `http://localhost:3000`) |
