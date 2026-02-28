# FlowPay — All Endpoints

**API base:** `http://localhost:8000`  
**Swagger UI:** `http://localhost:8000/docs` ← easiest way to try everything

> **Note for Windows PowerShell users:** `curl` on Windows is an alias for `Invoke-WebRequest`.  
> Use the **PowerShell** examples below, or install real curl: `winget install curl.curl`

---

## Account IDs (pre-seeded)
```
Alex  (payee / freelancer) → 69a268d595150878eaffa3ba
Jordan (payer / client)    → 69a268d595150878eaffa3bc
```

---

## 1. Create a Payment Request (Collect)

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/collects/" `
  -ContentType "application/json" `
  -Body '{
    "payee_account_id": "69a268d595150878eaffa3ba",
    "payer_account_id": "69a268d595150878eaffa3bc",
    "amount": 4900,
    "description": "Logo design invoice",
    "expires_at": "2026-03-10T00:00:00Z"
  }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/collects/", json={
    "payee_account_id": "69a268d595150878eaffa3ba",
    "payer_account_id": "69a268d595150878eaffa3bc",
    "amount": 4900,
    "description": "Logo design invoice",
    "expires_at": "2026-03-10T00:00:00Z",
})
print(r.json())  # → { "id": "clct_...", "status": "pending" }
```

**JavaScript / Node**
```js
const r = await fetch("http://localhost:8000/v1/collects/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    payee_account_id: "69a268d595150878eaffa3ba",
    payer_account_id: "69a268d595150878eaffa3bc",
    amount: 4900,
    description: "Logo design invoice",
    expires_at: "2026-03-10T00:00:00Z",
  }),
});
const data = await r.json();
console.log(data.id);  // save this for the next steps
```

---

## 2. Approve the Request → Nessie transfer fires

Replace `clct_YOUR_ID` with the `id` from step 1.

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/collects/clct_YOUR_ID/approve"
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/collects/clct_YOUR_ID/approve")
print(r.json())  # → { "status": "approved", "nessie_transfer_id": "..." }
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/collects/clct_YOUR_ID/approve", { method: "POST" });
console.log(await r.json());
```

---

## 3. Decline a Request

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/collects/clct_YOUR_ID/decline?reason=wrong_amount"
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/collects/clct_YOUR_ID/decline", params={"reason": "wrong_amount"})
print(r.json())
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/collects/clct_YOUR_ID/decline?reason=wrong_amount", { method: "POST" });
console.log(await r.json());
```

---

## 4. List a Payer's Inbox (with filtering)

**PowerShell**
```powershell
Invoke-RestMethod "http://localhost:8000/v1/collects/?payer_id=69a268d595150878eaffa3bc&status=pending&limit=10"
```

**Python**
```python
import httpx
r = httpx.get("http://localhost:8000/v1/collects/", params={
    "payer_id": "69a268d595150878eaffa3bc",
    "status": "pending",   # pending | approved | declined | expired
    "limit": 10,
    "offset": 0,
})
print(r.json())
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/collects/?payer_id=69a268d595150878eaffa3bc&status=pending");
console.log(await r.json());
```

---

## 5. Group Pool — Create

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/pools/" `
  -ContentType "application/json" `
  -Body '{
    "goal_amount": 20000,
    "description": "Team dinner",
    "organizer_account_id": "69a268d595150878eaffa3ba",
    "payee_account_id": "69a268d595150878eaffa3ba",
    "deadline": "2026-03-10T00:00:00Z",
    "on_deadline_miss": "refund_all"
  }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/pools/", json={
    "goal_amount": 20000,
    "description": "Team dinner",
    "organizer_account_id": "69a268d595150878eaffa3ba",
    "payee_account_id": "69a268d595150878eaffa3ba",
    "deadline": "2026-03-10T00:00:00Z",
    "on_deadline_miss": "refund_all",
})
print(r.json())  # → { "id": "pool_...", "status": "collecting" }
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/pools/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    goal_amount: 20000,
    description: "Team dinner",
    organizer_account_id: "69a268d595150878eaffa3ba",
    payee_account_id: "69a268d595150878eaffa3ba",
    deadline: "2026-03-10T00:00:00Z",
    on_deadline_miss: "refund_all",
  }),
});
console.log(await r.json());
```

---

## 6. Group Pool — Contribute

Run multiple times to fill the pool. Auto-settles when `collected_amount >= goal_amount`.

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/pools/pool_YOUR_ID/contribute" `
  -ContentType "application/json" `
  -Body '{ "payer_account_id": "69a268d595150878eaffa3bc", "amount": 5000 }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/pools/pool_YOUR_ID/contribute", json={
    "payer_account_id": "69a268d595150878eaffa3bc",
    "amount": 5000,  # $50.00
})
print(r.json())  # watch "status" → "funded" when goal hit
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/pools/pool_YOUR_ID/contribute", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ payer_account_id: "69a268d595150878eaffa3bc", amount: 5000 }),
});
console.log(await r.json());
```

---

## 7. Group Pool — Cancel (auto-refunds everyone)

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/pools/pool_YOUR_ID/cancel"
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/pools/pool_YOUR_ID/cancel")
print(r.json())  # → { "status": "cancelled", "refund_ids": ["nessie_tx_...", ...] }
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/pools/pool_YOUR_ID/cancel", { method: "POST" });
console.log(await r.json());
```

---

## 8. Cross-Border FX Corridor — Create (locks live exchange rate)

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/corridors/" `
  -ContentType "application/json" `
  -Body '{
    "source_currency": "inr",
    "target_currency": "usd",
    "source_account_id": "69a268d595150878eaffa3bc",
    "target_account_id": "69a268d595150878eaffa3ba",
    "amount_target": 4900,
    "description": "India to USA payment",
    "lock_duration_minutes": 30,
    "max_rate_drift_pct": 2.0
  }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/corridors/", json={
    "source_currency": "inr",
    "target_currency": "usd",
    "source_account_id": "69a268d595150878eaffa3bc",
    "target_account_id": "69a268d595150878eaffa3ba",
    "amount_target": 4900,       # receive $49.00
    "description": "India → USA",
    "lock_duration_minutes": 30,
    "max_rate_drift_pct": 2.0,
})
d = r.json()
print("Rate:", d["rate_lock"]["rate"])         # live INR→USD rate
print("Payer owes (INR cents):", d["amount_source_cents"])
print("Expires:", d["rate_lock"]["expires_at"])
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/corridors/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    source_currency: "inr", target_currency: "usd",
    source_account_id: "69a268d595150878eaffa3bc",
    target_account_id: "69a268d595150878eaffa3ba",
    amount_target: 4900,
    description: "India → USA",
    lock_duration_minutes: 30, max_rate_drift_pct: 2.0,
  }),
});
const d = await r.json();
console.log("Rate:", d.rate_lock.rate, "| Corridor ID:", d.id);
```

---

## 9. Cross-Border FX Corridor — Execute (remit)

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/corridors/crdr_YOUR_ID/remit"
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/corridors/crdr_YOUR_ID/remit")
print(r.json())  # → { "status": "remitted", "nessie_transfer_id": "..." }
```

**JavaScript**
```js
const r = await fetch("http://localhost:8000/v1/corridors/crdr_YOUR_ID/remit", { method: "POST" });
console.log(await r.json());
```

---

## 10. Multi-Currency FX Pool — Create

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/fxpools/" `
  -ContentType "application/json" `
  -Body '{
    "goal_amount_usd": 20000,
    "organizer_account_id": "69a268d595150878eaffa3ba",
    "payee_account_id": "69a268d595150878eaffa3ba",
    "description": "Global team expenses",
    "deadline": "2026-03-10T00:00:00Z",
    "max_rate_drift_pct": 3.0
  }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/fxpools/", json={
    "goal_amount_usd": 20000,
    "organizer_account_id": "69a268d595150878eaffa3ba",
    "payee_account_id": "69a268d595150878eaffa3ba",
    "description": "Global team expenses",
    "deadline": "2026-03-10T00:00:00Z",
    "max_rate_drift_pct": 3.0,
})
print(r.json())
```

---

## 11. Multi-Currency FX Pool — Contribute (in any currency)

**PowerShell**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/fxpools/fxpool_YOUR_ID/contribute" `
  -ContentType "application/json" `
  -Body '{ "payer_account_id": "69a268d595150878eaffa3bc", "currency": "eur", "amount_local": 4500 }'
```

**Python**
```python
import httpx
r = httpx.post("http://localhost:8000/v1/fxpools/fxpool_YOUR_ID/contribute", json={
    "payer_account_id": "69a268d595150878eaffa3bc",
    "currency": "eur",    # inr | eur | gbp | usd | jpy | cad ...
    "amount_local": 4500, # €45.00 — auto-converts to USD at live rate
})
print(r.json())  # → { "collected_usd": ..., "currencies_collected": ["EUR"] }
```

---

## Quick Reference — All Endpoints

| Method | Endpoint | What it does |
|--------|----------|--------------|
| GET | `/v1/health` | API health check |
| POST | `/v1/collects/` | Create pull payment request |
| GET | `/v1/collects/` | List (`?payer_id=&status=&limit=`) |
| GET | `/v1/collects/{id}` | Get single collect |
| POST | `/v1/collects/{id}/approve` | Approve → Nessie transfer |
| POST | `/v1/collects/{id}/decline` | Decline |
| POST | `/v1/pools/` | Create group pool |
| GET | `/v1/pools/{id}` | Get pool status |
| POST | `/v1/pools/{id}/contribute` | Add contribution |
| POST | `/v1/pools/{id}/cancel` | Cancel → auto-refund all |
| GET | `/v1/pools/{id}/contributions` | List individual contributions |
| POST | `/v1/corridors/` | Create FX corridor (live rate lock) |
| POST | `/v1/corridors/{id}/remit` | Execute corridor transfer |
| POST | `/v1/fxpools/` | Create multi-currency FX pool |
| POST | `/v1/fxpools/{id}/contribute` | Contribute in local currency |
| GET | `/v1/analytics/` | Platform metrics snapshot |

---

> **Tip:** The fastest way to explore is `http://localhost:8000/docs` — click any endpoint → "Try it out" → fill the form → "Execute". No curl or PowerShell needed.
