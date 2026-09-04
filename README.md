# RiskLens

**Real-time transaction risk scoring & simulated compliance automation.**
Built for the Razorpay AI Builder Internship 2026 — Track 2: AI Risk Manager.

RiskLens scores every transaction against nine independent, weighted risk
signals (amount anomaly, velocity, geo mismatch, impossible travel, new
device, high-risk merchant category, odd hour, new card, repeated failed
attempts) and produces a 0–100 score, a risk band, and a fully explainable
breakdown of exactly which signals fired and why — then simulates the
compliance action a real system would take at each band:

| Score | Band | Simulated Action |
|---|---|---|
| 0–24 | LOW | Auto-approve |
| 25–54 | MEDIUM | Flag & monitor (approved, logged) |
| 55–79 | HIGH | Send to manual review queue |
| 80–100 | CRITICAL | Auto-block |

Nothing here is a black box — every point on the score traces back to a
plain-English reason, which is the whole point of a *Risk Manager*, not
just a risk model: compliance teams need to be able to explain a block, not
just trust it.

## Why synthetic data

Razorpay understandably doesn't hand student applicants live production
transaction data, so `backend/app/generator.py` simulates a realistic
stream: 60 synthetic user profiles with their own spending habits, home
country, known devices, and card age, producing mostly-normal transactions
with ~14% injected fraud patterns (velocity bursts, impossible travel,
brand-new-device-plus-big-spend, card testing via repeated failures, etc).

Critically, **the scoring engine never sees the fraud label** — it only
receives engineered features, exactly like a real risk engine would. The
label is kept solely so the dashboard can report a "fraud catch rate" as a
sanity check on the rule weights.

## Architecture

```
risklens/
├── backend/                  FastAPI service (Python)
│   └── app/
│       ├── risk_engine.py    Explainable weighted scoring logic
│       ├── generator.py      Synthetic user + transaction generator
│       ├── database.py       SQLite persistence (audit trail)
│       └── main.py           API endpoints
└── frontend/                 React + Vite dashboard
    └── src/
        ├── App.jsx           Live feed, explainability panel, what-if tester
        └── index.css         Dashboard styling
```

**Backend → Frontend flow:** the dashboard's "Start Live Feed" button polls
`POST /api/simulate` roughly once a second, prepending each newly scored
transaction to the feed and updating aggregate stats. A "Test a Custom
Transaction" panel lets you hand-build a transaction (amount, category,
geo mismatch, new device, etc.) and see the score and factor breakdown for
that exact input — the fastest way to demo *why* a transaction was flagged.

## Running it locally

**Backend**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/simulate?count=N` | Generate + score N synthetic transactions |
| POST | `/api/score-custom` | Score a manually-specified "what-if" transaction |
| GET | `/api/transactions?limit=N` | Recent scored transactions |
| GET | `/api/transactions/{id}` | One transaction with full explainability |
| GET | `/api/stats` | Aggregate dashboard stats |

## What I'd build next with more time

- Swap the rule-based engine for a hybrid model: keep the rules for
  explainability, but layer a learned anomaly-detection model (e.g.
  isolation forest on engineered features) on top for signals a fixed
  rule set can't catch — then use the rules to explain the model's flags.
- Persist to Postgres instead of SQLite for concurrent writes at real scale.
- Replace polling with a WebSocket feed for true real-time push instead of
  ~1s client-side polling.
- Real device-fingerprinting and IP-geolocation inputs instead of synthetic
  booleans.
- Lock down CORS to the deployed frontend origin (wide open right now,
  intentionally, for local dev speed).
