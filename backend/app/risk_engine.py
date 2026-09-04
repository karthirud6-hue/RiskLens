"""
RiskLens explainable risk scoring engine.

Rule-based, weighted scoring model that mirrors how a real-world transaction
risk engine combines independent signals into a single explainable score.
Each triggered factor carries its own point contribution and a plain-English
rationale, so any score can be broken down for compliance review, disputes,
or audit -- nothing here is a black box.

Bands map directly to a simulated compliance action, the same way the
resolveai escalation engine mapped SLA breach severity to GREEN/YELLOW/
ORANGE/RED status:

    LOW      (0-24)   -> auto_approve
    MEDIUM   (25-54)  -> flag_and_monitor   (approved, logged for review)
    HIGH     (55-79)  -> manual_review      (held for a compliance queue)
    CRITICAL (80-100) -> auto_block
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any

HIGH_RISK_MERCHANT_CATEGORIES = {"gambling", "crypto", "jewelry", "money_transfer"}

# (low, high, band, action)
RISK_BANDS = [
    (80, 100, "CRITICAL", "auto_block"),
    (55, 79, "HIGH", "manual_review"),
    (25, 54, "MEDIUM", "flag_and_monitor"),
    (0, 24, "LOW", "auto_approve"),
]


@dataclass
class RiskFactor:
    code: str
    label: str
    points: float
    detail: str


@dataclass
class RiskResult:
    score: float
    band: str
    action: str
    factors: List[RiskFactor]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "band": self.band,
            "action": self.action,
            "factors": [asdict(f) for f in self.factors],
        }


def _band_for(score: float):
    for low, high, band, action in RISK_BANDS:
        if low <= score <= high:
            return band, action
    return "LOW", "auto_approve"


def score_transaction(txn: dict) -> RiskResult:
    """
    Expects an engineered-feature transaction dict:
      amount, user_avg_amount, merchant_category, hour_of_day,
      txn_count_last_hour, geo_mismatch, new_device, implied_speed_kmh,
      card_age_days, failed_attempts_before_success
    Missing fields are treated as the safest (lowest-risk) default.
    """
    factors: List[RiskFactor] = []

    # 1. Amount anomaly vs this user's historical average spend
    avg = max(float(txn.get("user_avg_amount") or 0), 1.0)
    amount = float(txn.get("amount") or 0)
    ratio = amount / avg
    if ratio >= 8:
        factors.append(RiskFactor(
            "amount_anomaly", "Amount far above user's average", 22,
            f"Rs.{amount:,.0f} is {ratio:.1f}x this user's typical spend (Rs.{avg:,.0f})"))
    elif ratio >= 4:
        factors.append(RiskFactor(
            "amount_anomaly", "Amount above user's average", 12,
            f"Rs.{amount:,.0f} is {ratio:.1f}x this user's typical spend (Rs.{avg:,.0f})"))

    # 2. Velocity - transactions from this user in the last hour
    velocity = int(txn.get("txn_count_last_hour") or 0)
    if velocity >= 6:
        factors.append(RiskFactor(
            "velocity_spike", "High transaction velocity", 20,
            f"{velocity} transactions from this user in the last hour"))
    elif velocity >= 3:
        factors.append(RiskFactor(
            "velocity_spike", "Elevated transaction velocity", 10,
            f"{velocity} transactions from this user in the last hour"))

    # 3. Geo mismatch between card/billing country and transaction origin
    if txn.get("geo_mismatch"):
        factors.append(RiskFactor(
            "geo_mismatch", "Billing/transaction geography mismatch", 18,
            "Card country and transaction origin country do not match"))

    # 4. Impossible travel between consecutive transactions
    speed = float(txn.get("implied_speed_kmh") or 0)
    if speed >= 800:
        factors.append(RiskFactor(
            "impossible_travel", "Impossible travel between transactions", 25,
            f"Implied travel speed of {speed:,.0f} km/h since this user's previous transaction"))

    # 5. Unrecognized device
    if txn.get("new_device"):
        factors.append(RiskFactor(
            "new_device", "Unrecognized device", 12,
            "Device fingerprint not previously seen for this user"))

    # 6. High-risk merchant category
    category = txn.get("merchant_category", "")
    if category in HIGH_RISK_MERCHANT_CATEGORIES:
        factors.append(RiskFactor(
            "high_risk_category", "High-risk merchant category", 10,
            f"Merchant category '{category}' has an elevated base fraud rate"))

    # 7. Odd hour (local)
    hour = int(txn.get("hour_of_day") if txn.get("hour_of_day") is not None else 12)
    if hour in (1, 2, 3, 4):
        factors.append(RiskFactor(
            "odd_hour", "Unusual transaction hour", 6,
            f"Transaction occurred at {hour:02d}:00 local time"))

    # 8. Newly issued card
    card_age = txn.get("card_age_days")
    card_age = 9999 if card_age is None else int(card_age)
    if card_age <= 3:
        factors.append(RiskFactor(
            "new_card", "Newly issued card", 10,
            f"Card is only {card_age} day(s) old"))

    # 9. Failed attempts immediately before this success
    failed = int(txn.get("failed_attempts_before_success") or 0)
    if failed >= 3:
        factors.append(RiskFactor(
            "failed_attempts", "Multiple failed attempts before success", 12,
            f"{failed} failed attempts immediately preceded this transaction"))
    elif failed >= 1:
        factors.append(RiskFactor(
            "failed_attempts", "Failed attempt(s) before success", 5,
            f"{failed} failed attempt(s) immediately preceded this transaction"))

    total = min(sum(f.points for f in factors), 100.0)
    band, action = _band_for(total)
    factors.sort(key=lambda f: f.points, reverse=True)
    return RiskResult(score=total, band=band, action=action, factors=factors)
