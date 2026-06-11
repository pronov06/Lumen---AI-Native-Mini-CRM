"""Seed data for a fictional D2C brand ("Lumen Coffee Co.").

This is deliberately *not* three rows of "John Doe". It generates a believable
customer base with real order histories so segments mean something: genuine VIPs
with long order streaks, lapsed buyers who went quiet, brand-new signups, and a
churning at-risk middle. Derived fields (totals, AOV, lifecycle stage) are
computed from the generated orders, not hand-waved — the same way the real app
would compute them on ingest.

Deterministic given a seed, so the hosted demo always looks the same.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

FIRST = ["Aarav", "Diya", "Vivaan", "Ananya", "Kabir", "Ishita", "Reyansh", "Sara",
         "Aditya", "Myra", "Arjun", "Anaya", "Vihaan", "Aadhya", "Krishna", "Pari",
         "Rohan", "Saanvi", "Dev", "Kiara", "Maya", "Liam", "Noah", "Emma", "Olivia",
         "Priya", "Rahul", "Neha", "Karan", "Tara", "Imran", "Zoya", "Joel", "Mira"]
LAST = ["Sharma", "Iyer", "Khan", "Reddy", "Nair", "Bose", "Mehta", "Gupta", "Rao",
        "Kapoor", "Das", "Menon", "Joshi", "Patel", "Chopra", "Sinha", "Verma",
        "Pillai", "Banerjee", "Fernandes", "Ahuja", "Saxena"]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune",
          "Kolkata", "Ahmedabad", "Jaipur"]
CHANNELS = ["whatsapp", "sms", "email", "rcs"]


def _stage(total_orders: int, days_since_last: int | None, total_spend: int) -> str:
    if total_orders == 0:
        return "new"
    if total_spend >= 40_000 and total_orders >= 6:
        return "vip"
    if days_since_last is None:
        return "new"
    if days_since_last > 90:
        return "lapsed"
    if days_since_last > 45:
        return "at_risk"
    return "active"


def generate(n_customers: int = 240, seed: int = 7,
             now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    customers: list[dict] = []
    orders: list[dict] = []

    for _ in range(n_customers):
        cid = f"cus_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        handle = name.lower().replace(" ", ".")
        signup_days_ago = rng.randint(1, 720)
        signup_at = now - timedelta(days=signup_days_ago)

        # Order count correlates with tenure but with a long tail of one-timers.
        if signup_days_ago < 21 and rng.random() < 0.5:
            n_orders = 0  # brand-new, no order yet
        else:
            n_orders = rng.choices([0, 1, 2, 3, 5, 8, 12],
                                   weights=[6, 22, 20, 16, 14, 12, 10])[0]

        cust_orders: list[dict] = []
        last_order_at: datetime | None = None
        total_spend = 0
        for _ in range(n_orders):
            placed = now - timedelta(days=rng.randint(0, signup_days_ago))
            amount = rng.choice([45000, 38000, 29900, 24900, 18900, 12900, 8900]) // 100 * 100
            amount = int(amount * rng.uniform(0.6, 1.6))
            total_spend += amount
            oid = f"ord_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
            cust_orders.append({"id": oid, "customer_id": cid, "amount": amount,
                                "placed_at": placed})
            last_order_at = placed if last_order_at is None else max(last_order_at, placed)

        days_since_last = (now - last_order_at).days if last_order_at else None
        avg_order_value = total_spend // n_orders if n_orders else 0
        stage = _stage(n_orders, days_since_last, total_spend)

        customers.append({
            "id": cid,
            "name": name,
            "email": f"{handle}@example.com",
            "phone": f"+9198{rng.randint(10000000, 99999999)}",
            "city": rng.choice(CITIES),
            "channel_optin": rng.choices(CHANNELS, weights=[40, 20, 30, 10])[0],
            "lifecycle_stage": stage,
            "total_orders": n_orders,
            "total_spend": total_spend,
            "avg_order_value": avg_order_value,
            "signup_at": signup_at,
            "last_order_at": last_order_at,
        })
        orders.extend(cust_orders)

    return customers, orders
