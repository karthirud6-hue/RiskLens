"""
Synthetic transaction generator.

Razorpay doesn't hand student builders live production transaction data, so
this module simulates a realistic stream: a pool of user profiles with their
own spending habits, home country, known devices and card age, producing
mostly-normal transactions with a configurable fraction of injected fraud
patterns (velocity bursts, impossible travel, brand-new device + big spend,
card testing via repeated failures, etc).

The risk engine (risk_engine.py) never sees the `_ground_truth_fraud` label
below -- it only sees engineered features, exactly like a real scoring
engine would. The label is kept purely so the dashboard can show a
"precision/recall against injected fraud" stat as a sanity check.
"""

import random
import time
import uuid
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

MERCHANT_CATEGORIES = [
    "grocery", "electronics", "travel", "gambling", "crypto",
    "jewelry", "utilities", "food", "fashion", "money_transfer", "other",
]

FRAUD_CATEGORIES = ["gambling", "crypto", "jewelry", "money_transfer"]

COUNTRIES = ["IN", "US", "UK", "AE", "SG", "NG", "RU", "BR"]

CITY_COORDS = {
    "IN": (19.07, 72.87),
    "US": (40.71, -74.00),
    "UK": (51.51, -0.13),
    "AE": (25.20, 55.27),
    "SG": (1.35, 103.82),
    "NG": (6.52, 3.38),
    "RU": (55.75, 37.62),
    "BR": (-23.55, -46.63),
}

FRAUD_RATE = 0.14


def _haversine_km(c1, c2):
    lat1, lon1 = c1
    lat2, lon2 = c2
    R = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


class UserProfile:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.home_country = "IN"
        self.avg_amount = round(random.uniform(300, 4000), 2)
        self.known_device = f"device-{uuid.uuid4().hex[:8]}"
        self.card_age_days = random.randint(30, 1500)
        self.last_txn_time = time.time() - random.uniform(3600, 86400)
        self.last_country = self.home_country
        self.txn_times_last_hour = []


USER_POOL = [UserProfile(f"user_{i:04d}") for i in range(60)]


def generate_transaction(force_fraud: bool | None = None) -> dict:
    user = random.choice(USER_POOL)
    now = time.time()
    is_fraud = force_fraud if force_fraud is not None else (random.random() < FRAUD_RATE)

    hour = datetime.now().hour
    user.txn_times_last_hour = [t for t in user.txn_times_last_hour if now - t < 3600]

    if is_fraud:
        amount = round(user.avg_amount * random.uniform(6, 15), 2)
        new_device = True
        geo_mismatch = True
        country = random.choice([c for c in COUNTRIES if c != user.home_country])
        dist = _haversine_km(CITY_COORDS[user.last_country], CITY_COORDS[country])
        elapsed_hr = max((now - user.last_txn_time) / 3600, 0.05)
        implied_speed = dist / elapsed_hr
        failed_attempts = random.choice([0, 0, 1, 2, 4])
        category = random.choice(FRAUD_CATEGORIES)
        for _ in range(random.randint(3, 7)):
            user.txn_times_last_hour.append(now - random.uniform(0, 3000))
        card_age = random.choice([user.card_age_days, random.randint(0, 2)])
    else:
        amount = round(max(random.gauss(user.avg_amount, user.avg_amount * 0.3), 20), 2)
        new_device = random.random() < 0.03
        geo_mismatch = False
        country = user.home_country
        implied_speed = 0.0
        failed_attempts = 1 if random.random() < 0.05 else 0
        category = random.choice(MERCHANT_CATEGORIES)
        card_age = user.card_age_days
        user.txn_times_last_hour.append(now)

    txn = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "amount": amount,
        "user_avg_amount": user.avg_amount,
        "merchant_category": category,
        "hour_of_day": hour,
        "txn_count_last_hour": len(user.txn_times_last_hour),
        "geo_mismatch": geo_mismatch,
        "new_device": new_device,
        "implied_speed_kmh": round(implied_speed, 1),
        "card_age_days": card_age,
        "failed_attempts_before_success": failed_attempts,
        "is_international": country != user.home_country,
        "country": country,
        "ground_truth_fraud": is_fraud,
    }

    user.last_txn_time = now
    user.last_country = country
    return txn
