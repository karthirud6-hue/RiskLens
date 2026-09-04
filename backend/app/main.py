"""
RiskLens API -- real-time transaction risk scoring & simulated compliance
automation, built for the Razorpay AI Builder Internship (AI Risk Manager
track).

Endpoints:
    POST /api/simulate            generate + score N synthetic transactions
    POST /api/score-custom        score a manually-entered "what-if" transaction
    GET  /api/transactions        recent scored transactions (feed)
    GET  /api/transactions/{id}   single transaction with full explainability
    GET  /api/stats               aggregate dashboard stats
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import database
from .generator import generate_transaction
from .risk_engine import score_transaction

app = FastAPI(title="RiskLens API", version="0.1.0")

# Demo-scoped: wide open CORS so the Vite dev server can call this freely.
# A production deployment would restrict this to the dashboard's real origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    database.init_db()


class CustomTransaction(BaseModel):
    amount: float = Field(..., gt=0)
    user_avg_amount: float = Field(1000, gt=0)
    merchant_category: str = "grocery"
    hour_of_day: int = Field(12, ge=0, le=23)
    txn_count_last_hour: int = Field(0, ge=0)
    geo_mismatch: bool = False
    new_device: bool = False
    implied_speed_kmh: float = Field(0, ge=0)
    card_age_days: int = Field(365, ge=0)
    failed_attempts_before_success: int = Field(0, ge=0)


@app.post("/api/simulate")
def simulate(count: int = Query(1, ge=1, le=50)):
    results = []
    for _ in range(count):
        txn = generate_transaction()
        result = score_transaction(txn).to_dict()
        database.insert_scored_transaction(txn, result, source="simulated")
        results.append({**txn, **result})
    return {"generated": results}


@app.post("/api/score-custom")
def score_custom(payload: CustomTransaction):
    import uuid
    from datetime import datetime

    txn = payload.model_dump()
    txn["id"] = str(uuid.uuid4())
    txn["user_id"] = "manual_test"
    txn["timestamp"] = datetime.now().isoformat(timespec="seconds")
    txn["country"] = "IN" if not payload.geo_mismatch else "US"
    txn["is_international"] = payload.geo_mismatch
    txn["ground_truth_fraud"] = False

    result = score_transaction(txn).to_dict()
    database.insert_scored_transaction(txn, result, source="manual_test")
    return {**txn, **result}


@app.get("/api/transactions")
def list_transactions(limit: int = Query(50, ge=1, le=200)):
    return {"transactions": database.recent_transactions(limit)}


@app.get("/api/transactions/{txn_id}")
def get_transaction(txn_id: str):
    txn = database.get_transaction(txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@app.get("/api/stats")
def get_stats():
    return database.stats()


@app.get("/api/health")
def health():
    return {"status": "ok"}
