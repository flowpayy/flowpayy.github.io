"""
FlowPay API — Python Snippets
==============================
Copy any block below and run it. Each one is standalone.
Requires: pip install httpx  (or pip install requests)

The API is running at: http://localhost:8000
Interactive docs at:   http://localhost:8000/docs
"""

import httpx  # or: import requests and swap httpx.post → requests.post

BASE = "http://localhost:8000"

# Account IDs (seeded via: cd backend && python seed.py)
ALEX   = "69a268d595150878eaffa3ba"   # Payee / Freelancer
JORDAN = "69a268d595150878eaffa3bc"   # Payer / Client

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/v1/health")
print(r.json())

# ─────────────────────────────────────────────────────────────────────────────
# CREATE A COLLECT (pull payment request)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/v1/collects/", json={
    "payee_account_id": ALEX,
    "payer_account_id": JORDAN,
    "amount": 4900,                           # $49.00 (cents)
    "description": "Logo design invoice",
    "expires_at": "2026-03-10T00:00:00Z",
})
collect = r.json()
print(collect)
COLLECT_ID = collect["id"]

# ─────────────────────────────────────────────────────────────────────────────
# GET A COLLECT
# ─────────────────────────────────────────────────────────────────────────────
COLLECT_ID = "clct_YOUR_ID_HERE"   # paste from above
r = httpx.get(f"{BASE}/v1/collects/{COLLECT_ID}")
print(r.json())

# ─────────────────────────────────────────────────────────────────────────────
# LIST COLLECTS (filter Jordan's pending inbox)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/v1/collects/", params={
    "payer_id": JORDAN,
    "status": "pending",   # pending | approved | declined | expired
    "limit": 10,
    "offset": 0,
})
print(r.json())

# ─────────────────────────────────────────────────────────────────────────────
# APPROVE A COLLECT  →  triggers real Nessie transfer
# ─────────────────────────────────────────────────────────────────────────────
COLLECT_ID = "clct_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/collects/{COLLECT_ID}/approve")
print(r.json())   # → { status: "approved", nessie_transfer_id: "..." }

# ─────────────────────────────────────────────────────────────────────────────
# DECLINE A COLLECT
# ─────────────────────────────────────────────────────────────────────────────
COLLECT_ID = "clct_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/collects/{COLLECT_ID}/decline", params={"reason": "wrong_amount"})
print(r.json())

# ─────────────────────────────────────────────────────────────────────────────
# CREATE A POOL
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/v1/pools/", json={
    "goal_amount": 20000,                     # $200.00
    "description": "Team dinner",
    "organizer_account_id": ALEX,
    "payee_account_id": ALEX,
    "deadline": "2026-03-10T00:00:00Z",
    "on_deadline_miss": "refund_all",
})
pool = r.json()
print(pool)
POOL_ID = pool["id"]

# ─────────────────────────────────────────────────────────────────────────────
# CONTRIBUTE TO A POOL
# ─────────────────────────────────────────────────────────────────────────────
POOL_ID = "pool_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/pools/{POOL_ID}/contribute", json={
    "payer_account_id": JORDAN,
    "amount": 5000,                           # $50.00
})
print(r.json())   # watch collected_amount go up; status → "funded" when goal hit

# ─────────────────────────────────────────────────────────────────────────────
# CANCEL POOL  →  triggers auto-refund to all contributors
# ─────────────────────────────────────────────────────────────────────────────
POOL_ID = "pool_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/pools/{POOL_ID}/cancel")
print(r.json())   # → { status: "cancelled", refund_ids: ["..."] }

# ─────────────────────────────────────────────────────────────────────────────
# CREATE FX CORRIDOR  (cross-border with live rate lock)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/v1/corridors/", json={
    "source_currency": "inr",
    "target_currency": "usd",
    "source_account_id": JORDAN,
    "target_account_id": ALEX,
    "amount_target": 4900,                    # receive $49.00 USD
    "description": "India → USA payment",
    "lock_duration_minutes": 30,
    "max_rate_drift_pct": 2.0,
})
corridor = r.json()
print(corridor)   # → see live rate, source amount in INR, expiry
CORRIDOR_ID = corridor["id"]

# ─────────────────────────────────────────────────────────────────────────────
# REMIT (execute) THE CORRIDOR
# ─────────────────────────────────────────────────────────────────────────────
CORRIDOR_ID = "crdr_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/corridors/{CORRIDOR_ID}/remit")
print(r.json())   # → { status: "remitted", nessie_transfer_id: "..." }

# ─────────────────────────────────────────────────────────────────────────────
# CREATE FX POOL  (multi-currency group collection)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/v1/fxpools/", json={
    "goal_amount_usd": 20000,                 # $200 USD goal
    "organizer_account_id": ALEX,
    "payee_account_id": ALEX,
    "description": "Global team expenses",
    "deadline": "2026-03-10T00:00:00Z",
    "max_rate_drift_pct": 3.0,
})
fxpool = r.json()
print(fxpool)
FXPOOL_ID = fxpool["id"]

# ─────────────────────────────────────────────────────────────────────────────
# CONTRIBUTE TO FX POOL (in local currency — auto converts to USD)
# ─────────────────────────────────────────────────────────────────────────────
FXPOOL_ID = "fxpool_YOUR_ID_HERE"
r = httpx.post(f"{BASE}/v1/fxpools/{FXPOOL_ID}/contribute", json={
    "payer_account_id": JORDAN,
    "currency": "inr",                        # inr | eur | gbp | usd | jpy ...
    "amount_local": 4100,                     # ₹41.00
})
print(r.json())   # → shows collected_usd, currencies_collected

# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.get(f"{BASE}/v1/analytics/")
print(r.json())

# ─────────────────────────────────────────────────────────────────────────────
# USING IDEMPOTENCY KEY  (same POST twice = same response, no duplicate)
# ─────────────────────────────────────────────────────────────────────────────
for _ in range(2):
    r = httpx.post(
        f"{BASE}/v1/collects/",
        headers={"Idempotency-Key": "my-unique-key-42"},
        json={
            "payee_account_id": ALEX,
            "payer_account_id": JORDAN,
            "amount": 2500,
            "description": "Idempotency test",
            "expires_at": "2026-03-10T00:00:00Z",
        }
    )
    print(r.headers.get("X-Idempotency-Replayed"), r.json()["id"])
    # First call:  None (or "false")  clct_abc
    # Second call: "true"             clct_abc  (same ID!)
