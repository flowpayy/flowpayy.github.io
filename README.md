# ⚡ FlowPay — The Payment Primitives Stripe Doesn't Have

> _"A billion people in India and China use pull payments and group collection every day. No Western payment API exposes them as first-class developer primitives. FlowPay does."_  
> Built at **HackIllinois 2026** · Stripe Track · Capital One Nessie Prize

---

## 🚀 How to Run Everything

Clone the repo first:
```bash
git clone https://github.com/flowpayy/flowpayy.github.io.git
cd flowpayy.github.io
```

### Terminal 1 — Backend API (required)
```bash
cd backend
pip install fastapi uvicorn httpx pydantic requests
python -m uvicorn app.main:app --reload --port 8000
```
✅ API live at: **http://localhost:8000**  
✅ Swagger docs: **http://localhost:8000/docs**

### Terminal 2 — Seed Demo Accounts (run once)
```bash
cd backend
python seed.py
```
This creates `Alex` (payee) and `Jordan` (payer) in Capital One Nessie sandbox with real account IDs.

### Terminal 3 — Frontend Dashboard (optional)
```bash
cd frontend2
npm install
npm run dev
```
✅ Dashboard at: **http://localhost:5173**

### Terminal 4 — Docs & Pitch Site (optional)
```bash
python -m http.server 3000 --directory docs
```
✅ Pitch at: **http://localhost:3000/pitch.html**  
✅ Judge guide: **http://localhost:3000/judge-guide.html**

### Check API is live (PowerShell)
```powershell
Invoke-RestMethod "http://localhost:8000/v1/health"
```

### Run the Python demo (all scenarios end-to-end)
```bash
pip install httpx
python demo.py
```

### Demo Account IDs (paste into any endpoint)
```
Alex  (payee / freelancer) → 69a268d595150878eaffa3ba
Jordan (payer / client)    → 69a268d595150878eaffa3bc
```

> **See [`ENDPOINTS.md`](./ENDPOINTS.md)** for PowerShell, Python, and JavaScript code for every endpoint.

---


## What is FlowPay?

FlowPay is a payment API that exposes three primitives missing from every Western payment platform:

| Primitive | Inspired By | What It Does |
|-----------|-------------|--------------|
| **Collect** | UPI Collect | Receiver-initiated pull payment — payee requests, payer approves |
| **Pool** | Alipay AA Split | Group collection with auto-refund if deadline passes |
| **FlowBridge** | UPI Cross-Border + Wise | Multi-currency corridors with FX rate locking & drift-triggered refunds |

---

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+

### 1. Start the Backend

```bash
cd backend
pip install fastapi uvicorn httpx pydantic requests
python -m uvicorn app.main:app --reload --port 8000
```

API is now live at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### 2. Seed Demo Accounts (Capital One Nessie)

```bash
cd backend
python seed.py
```

This creates two real Nessie accounts (Alex the freelancer, Jordan the client) with starting balance.

### 3. Start the Dev Dashboard (optional)

```bash
cd frontend2
npm install
npm run dev
```

Dashboard at `http://localhost:5173`

### 4. Start the Pitch/Docs Site (optional)

```bash
python -m http.server 3000 --directory docs
```

Docs at `http://localhost:3000`

---

## API Reference

Base URL: `http://localhost:8000`  
All responses are JSON. All amounts are in **integer cents** (e.g. `4900` = `$49.00`).

### Authentication
For the hackathon demo, no auth header is required. In production, this would use Bearer tokens.

### Idempotency
All `POST` endpoints accept an optional `Idempotency-Key` header. Supplying the same key twice returns the original response without creating a duplicate resource.

```bash
curl -X POST http://localhost:8000/v1/collects \
  -H "Idempotency-Key: my-unique-key-123" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

---

### Health Check

```
GET /v1/health
```

```bash
curl http://localhost:8000/v1/health
```

```json
{ "status": "ok", "message": "FlowPay API is healthy and running." }
```

---

## Primitive 1: Collect (Pull Payment Request)

A payee sends a payment request. The payer sees it in their programmable inbox and approves or declines. Money only moves on explicit payer approval. No equivalent exists in Stripe.

### Create a Collect

```
POST /v1/collects
```

**Body:**
```json
{
  "payee_account_id": "nessie_acc_alex",
  "payer_account_id": "nessie_acc_jordan",
  "amount": 4900,
  "currency": "usd",
  "description": "Logo design — Phase 1",
  "expires_at": "2026-03-05T00:00:00Z",
  "metadata": { "invoice_id": "inv_789" }
}
```

**curl:**
```bash
curl -X POST http://localhost:8000/v1/collects \
  -H "Content-Type: application/json" \
  -d '{
    "payee_account_id": "69a268d595150878eaffa3ba",
    "payer_account_id": "69a268d595150878eaffa3bc",
    "amount": 4900,
    "description": "Logo design",
    "expires_at": "2026-03-10T00:00:00Z"
  }'
```

**Response `201`:**
```json
{
  "id": "clct_9e2197a119f5",
  "status": "pending",
  "amount": 4900,
  "currency": "usd",
  "description": "Logo design — Phase 1",
  "payee_account_id": "...",
  "payer_account_id": "...",
  "expires_at": "2026-03-05T00:00:00Z",
  "created_at": "2026-02-28T04:00:00Z",
  "approved_at": null,
  "nessie_transfer_id": null
}
```

### List Collects (Payer Inbox)

```
GET /v1/collects?payer_id=ACCOUNT_ID&status=pending&limit=10&offset=0
```

Query params: `payer_id`, `payee_id`, `status` (pending|approved|declined|expired), `limit` (default 20), `offset`

```bash
curl "http://localhost:8000/v1/collects?payer_id=69a268d595150878eaffa3bc&status=pending"
```

### Get a Collect

```
GET /v1/collects/{id}
```

### Approve a Collect

```
POST /v1/collects/{id}/approve
```

FlowPay checks the payer's Nessie balance, executes a real Capital One Nessie transfer, returns a `nessie_transfer_id`, and fires the `collect.approved` webhook.

```bash
curl -X POST http://localhost:8000/v1/collects/clct_abc123/approve
```

### Decline a Collect

```
POST /v1/collects/{id}/decline?reason=wrong_amount
```

---

## Primitive 2: Pool (Group Collection)

Collect from N participants toward a goal. Settle only when funded. Auto-refund everyone if the deadline passes unfunded.

### Create a Pool

```
POST /v1/pools
```

```bash
curl -X POST http://localhost:8000/v1/pools \
  -H "Content-Type: application/json" \
  -d '{
    "goal_amount": 20000,
    "description": "Dinner at Au Cheval",
    "organizer_account_id": "69a268d595150878eaffa3ba",
    "payee_account_id": "69a268d595150878eaffa3ba",
    "deadline": "2026-03-01T00:00:00Z"
  }'
```

### Contribute to a Pool

```
POST /v1/pools/{id}/contribute
```

```bash
curl -X POST http://localhost:8000/v1/pools/pool_abc123/contribute \
  -H "Content-Type: application/json" \
  -d '{"payer_account_id": "69a268d595150878eaffa3bc", "amount": 5000}'
```

### Cancel a Pool (triggers auto-refund)

```
POST /v1/pools/{id}/cancel
```

All contributors receive a reverse Nessie transfer automatically.

---

## Primitive 3: FlowBridge (Cross-Border FX Corridors)

The primitive that Stripe + Capital One could build together — cross-border payment corridors with programmable FX rate locking and multi-currency group collection.

### Create a Corridor (INR → USD with rate lock)

```
POST /v1/corridors
```

```bash
curl -X POST http://localhost:8000/v1/corridors \
  -H "Content-Type: application/json" \
  -d '{
    "source_currency": "inr",
    "target_currency": "usd",
    "source_account_id": "69a268d595150878eaffa3bc",
    "target_account_id": "69a268d595150878eaffa3ba",
    "amount_target": 4900,
    "description": "Freelancer payment: India to USA",
    "lock_duration_minutes": 30,
    "max_rate_drift_pct": 2.0
  }'
```

**Response:** Live exchange rate locked for 30 minutes, equivalent INR amount quoted.

### Execute the Corridor Transfer

```
POST /v1/corridors/{id}/remit
```

Validates rate still within drift tolerance → executes Nessie transfer → fires `corridor.settled` webhook.

### Create an FX Pool (Multi-Currency Group Collection)

```
POST /v1/fxpools
```

```bash
curl -X POST http://localhost:8000/v1/fxpools \
  -H "Content-Type: application/json" \
  -d '{
    "goal_amount_usd": 20000,
    "organizer_account_id": "ACC_ID",
    "payee_account_id": "ACC_ID",
    "description": "International team dinner",
    "deadline": "2026-03-01T00:00:00Z",
    "max_rate_drift_pct": 3.0
  }'
```

### FX Pool Contribute (in any currency)

```
POST /v1/fxpools/{id}/contribute
```

```bash
curl -X POST http://localhost:8000/v1/fxpools/fxpool_abc/contribute \
  -H "Content-Type: application/json" \
  -d '{"payer_account_id": "ACC_ID", "currency": "inr", "amount_local": 4100}'
```

Each contribution locks the live FX rate at time of payment. If rates drift >3% before settlement, **everyone is refunded in their original currency**.

---

## Additional Endpoints

### Recurring Collect (Pre-Authorized Subscription Pull)

```
POST /v1/recurring          — Create a recurring payment authorization
POST /v1/recurring/{id}/trigger  — Execute one occurrence (would be cron in prod)
POST /v1/recurring/{id}/pause    — Pause without cancelling
POST /v1/recurring/{id}/cancel   — Cancel permanently
```

### Webhooks

```
POST /v1/webhooks           — Register a webhook URL
```

Events fired:
- `collect.approved`, `collect.declined`, `collect.expired`
- `pool.goal_reached`, `pool.cancelled`, `pool.expired_refunded`
- `corridor.rate_locked`, `corridor.settled`, `corridor.drift_cancelled`
- `fxpool.contribution_received`, `fxpool.goal_reached`, `fxpool.rate_drifted`

### Analytics

```
GET /v1/analytics           — Real-time platform volume, statuses, counts
```

---

## Error Handling

All errors follow a consistent shape:

```json
{
  "detail": {
    "error": {
      "type": "invalid_request_error",
      "code": "collect_expired",
      "message": "This collect request expired on 2026-03-01T00:00:00Z.",
      "param": null,
      "expired_at": "2026-03-01T00:00:00Z"
    }
  }
}
```

| Status | Code | When |
|--------|------|------|
| `400` | `invalid_status` | Approving an already-declined collect |
| `402` | `insufficient_funds` | Payer balance too low |
| `404` | `not_found` | Resource ID doesn't exist |
| `409` | `duplicate_idempotency_key` | Same key sent twice |
| `410` | `collect_expired` | Collect/corridor past its expiry |
| `422` | `rate_drift_exceeded` | FX moved beyond tolerance |
| `500` | `nessie_transfer_failed` | Banking layer error |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | **FastAPI** (Python 3.11) |
| API Validation | **Pydantic v2** |
| API Server | **Uvicorn** (ASGI) |
| Banking Layer | **Capital One Nessie API** |
| FX Rates | **open.er-api.com** (live rates) |
| Frontend Dashboard | **React + Vite** |
| Docs Site | **Vanilla HTML/CSS** |

---

## Filtering & Pagination

All list endpoints support:

| Param | Description | Default |
|-------|-------------|---------|
| `limit` | Max items to return | 20 |
| `offset` | Items to skip | 0 |
| `status` | Filter by status | all |
| `payer_id` | Filter to specific payer | — |
| `payee_id` | Filter to specific payee | — |

---

## State Machines

### Collect
```
pending → approved (Nessie transfer executed)
pending → declined (payer declined)
pending → expired  (deadline passed without action)
```

### Pool
```
collecting → funded    (goal reached, settled to payee)
collecting → cancelled (organizer cancelled, contributors refunded)
collecting → expired   (deadline passed, contributors refunded)
```

### Corridor (FlowBridge)
```
rate_locked → remitted        (FX transfer executed)
rate_locked → expired         (30-min lock timed out)
rate_locked → drift_cancelled (FX rate moved beyond tolerance)
```

### FX Pool (FlowBridge)
```
collecting → funded        (goal reached, all FX converted, settled)
collecting → drift_refunded (rate moved too far, all refunded in original currency)
collecting → cancelled     (organizer cancelled, all refunded)
```

---

## Demo Accounts (seeded via `seed.py`)

```
Alex (Payee / Freelancer): 69a268d595150878eaffa3ba
Jordan (Payer / Client):   69a268d595150878eaffa3bc
```

---

## Repository Structure

```
hackillonni/
├── backend/
│   ├── app/
│   │   ├── main.py           ← FastAPI app entry point
│   │   ├── models/
│   │   │   └── schemas.py    ← Pydantic request/response models
│   │   ├── api/
│   │   │   ├── collect.py    ← Collect endpoints
│   │   │   ├── pool.py       ← Pool endpoints
│   │   │   ├── corridor.py   ← FlowBridge corridor endpoints
│   │   │   ├── fxpool.py     ← FlowBridge FX pool endpoints
│   │   │   ├── recurring.py  ← Recurring collect endpoints
│   │   │   ├── analytics.py  ← Analytics endpoint
│   │   │   └── webhook.py    ← Webhook registration + dispatch
│   │   └── services/
│   │       ├── nessie.py     ← Capital One Nessie API client
│   │       └── fx.py         ← FX rate fetching + rate lock logic
│   └── seed.py               ← Demo account seeding script
├── frontend2/                ← React developer dashboard
├── docs/
│   └── index.html            ← Pitch site + full docs
└── README.md                 ← This file
```
