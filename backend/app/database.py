"""
Minimal SQLite persistence layer -- deliberately dependency-light (stdlib
sqlite3 only) so the whole backend runs with nothing beyond FastAPI +
uvicorn installed. Good enough for a demo/audit trail; a production build
would move this to a real Postgres ledger with proper migrations.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "risklens.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    amount REAL NOT NULL,
    user_avg_amount REAL,
    merchant_category TEXT,
    country TEXT,
    is_international INTEGER,
    hour_of_day INTEGER,
    txn_count_last_hour INTEGER,
    geo_mismatch INTEGER,
    new_device INTEGER,
    implied_speed_kmh REAL,
    card_age_days INTEGER,
    failed_attempts_before_success INTEGER,
    ground_truth_fraud INTEGER,
    score REAL NOT NULL,
    band TEXT NOT NULL,
    action TEXT NOT NULL,
    factors_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'simulated'
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def insert_scored_transaction(txn: Dict[str, Any], result_dict: Dict[str, Any], source: str = "simulated") -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO transactions (
            id, user_id, timestamp, amount, user_avg_amount, merchant_category,
            country, is_international, hour_of_day, txn_count_last_hour,
            geo_mismatch, new_device, implied_speed_kmh, card_age_days,
            failed_attempts_before_success, ground_truth_fraud,
            score, band, action, factors_json, source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            txn["id"], txn["user_id"], txn["timestamp"], txn["amount"],
            txn.get("user_avg_amount"), txn.get("merchant_category"),
            txn.get("country"), int(bool(txn.get("is_international"))),
            txn.get("hour_of_day"), txn.get("txn_count_last_hour"),
            int(bool(txn.get("geo_mismatch"))), int(bool(txn.get("new_device"))),
            txn.get("implied_speed_kmh"), txn.get("card_age_days"),
            txn.get("failed_attempts_before_success"),
            int(bool(txn.get("ground_truth_fraud", False))),
            result_dict["score"], result_dict["band"], result_dict["action"],
            json.dumps(result_dict["factors"]), source,
        ),
    )
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["factors"] = json.loads(d.pop("factors_json"))
    d["geo_mismatch"] = bool(d["geo_mismatch"])
    d["new_device"] = bool(d["new_device"])
    d["is_international"] = bool(d["is_international"])
    d["ground_truth_fraud"] = bool(d["ground_truth_fraud"])
    return d


def recent_transactions(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC, rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_transaction(txn_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def stats() -> Dict[str, Any]:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    by_band = {
        r["band"]: r["c"]
        for r in conn.execute("SELECT band, COUNT(*) c FROM transactions GROUP BY band").fetchall()
    }
    avg_score_row = conn.execute("SELECT AVG(score) a FROM transactions").fetchone()
    avg_score = round(avg_score_row["a"], 1) if avg_score_row["a"] is not None else 0.0

    # Sanity-check stat: how well did the engine's action line up with the
    # injected ground-truth fraud label. Not used by the engine itself.
    tp = conn.execute(
        "SELECT COUNT(*) c FROM transactions WHERE ground_truth_fraud=1 AND band IN ('HIGH','CRITICAL')"
    ).fetchone()["c"]
    fraud_total = conn.execute("SELECT COUNT(*) c FROM transactions WHERE ground_truth_fraud=1").fetchone()["c"]
    recall = round(100 * tp / fraud_total, 1) if fraud_total else None

    conn.close()
    return {
        "total": total,
        "by_band": {b: by_band.get(b, 0) for b in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
        "avg_score": avg_score,
        "fraud_catch_rate_pct": recall,
    }
