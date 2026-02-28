/**
 * FlowPay API — Node.js / JavaScript Snippets
 * =============================================
 * Copy any block and run it individually.
 *
 * Node.js: node try_node.js   (Node 18+ has fetch built-in)
 * Browser: paste the fetch() blocks in DevTools console
 *
 * API: http://localhost:8000
 * Docs: http://localhost:8000/docs
 */

const BASE = "http://localhost:8000";

// Account IDs (seeded via: cd backend && python seed.py)
const ALEX = "69a268d595150878eaffa3ba";  // Payee / Freelancer
const JORDAN = "69a268d595150878eaffa3bc";  // Payer / Client


// ─────────────────────────────────────────────────────────────────────────────
// HEALTH CHECK
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/health`)
    .then(r => r.json())
    .then(console.log);


// ─────────────────────────────────────────────────────────────────────────────
// CREATE A COLLECT  (pull payment request)
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/collects/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        payee_account_id: ALEX,
        payer_account_id: JORDAN,
        amount: 4900,                       // $49.00 in cents
        description: "Logo design invoice",
        expires_at: "2026-03-10T00:00:00Z",
    }),
})
    .then(r => r.json())
    .then(data => {
        console.log(data);
        console.log("Collect ID:", data.id);  // save this for the next calls
    });


// ─────────────────────────────────────────────────────────────────────────────
// GET A COLLECT
// ─────────────────────────────────────────────────────────────────────────────
const COLLECT_ID = "clct_YOUR_ID_HERE";   // paste from above
fetch(`${BASE}/v1/collects/${COLLECT_ID}`)
    .then(r => r.json())
    .then(console.log);


// ─────────────────────────────────────────────────────────────────────────────
// LIST COLLECTS (filter payer + status, with pagination)
// ─────────────────────────────────────────────────────────────────────────────
const params = new URLSearchParams({ payer_id: JORDAN, status: "pending", limit: 10 });
fetch(`${BASE}/v1/collects/?${params}`)
    .then(r => r.json())
    .then(console.log);


// ─────────────────────────────────────────────────────────────────────────────
// APPROVE A COLLECT  →  real Nessie transfer fires
// ─────────────────────────────────────────────────────────────────────────────
const COLLECT_ID = "clct_YOUR_ID_HERE";
fetch(`${BASE}/v1/collects/${COLLECT_ID}/approve`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
        console.log("Status:", data.status);               // "approved"
        console.log("Nessie TX:", data.nessie_transfer_id);
    });


// ─────────────────────────────────────────────────────────────────────────────
// DECLINE A COLLECT
// ─────────────────────────────────────────────────────────────────────────────
const COLLECT_ID = "clct_YOUR_ID_HERE";
fetch(`${BASE}/v1/collects/${COLLECT_ID}/decline?reason=wrong_amount`, { method: "POST" })
    .then(r => r.json())
    .then(console.log);


// ─────────────────────────────────────────────────────────────────────────────
// CREATE A POOL
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/pools/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        goal_amount: 20000,              // $200.00
        description: "Team dinner",
        organizer_account_id: ALEX,
        payee_account_id: ALEX,
        deadline: "2026-03-10T00:00:00Z",
        on_deadline_miss: "refund_all",
    }),
})
    .then(r => r.json())
    .then(data => {
        console.log(data);
        console.log("Pool ID:", data.id);
    });


// ─────────────────────────────────────────────────────────────────────────────
// CONTRIBUTE TO A POOL  (auto-settles when goal reached)
// ─────────────────────────────────────────────────────────────────────────────
const POOL_ID = "pool_YOUR_ID_HERE";
fetch(`${BASE}/v1/pools/${POOL_ID}/contribute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payer_account_id: JORDAN, amount: 5000 }), // $50.00
})
    .then(r => r.json())
    .then(data => {
        console.log("Collected:", data.collected_amount / 100, "of", data.goal_amount / 100);
        console.log("Status:", data.status);  // "collecting" or "funded"
    });


// ─────────────────────────────────────────────────────────────────────────────
// CANCEL POOL  →  auto-refunds all contributors via Nessie
// ─────────────────────────────────────────────────────────────────────────────
const POOL_ID = "pool_YOUR_ID_HERE";
fetch(`${BASE}/v1/pools/${POOL_ID}/cancel`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
        console.log("Status:", data.status);         // "cancelled"
        console.log("Refund IDs:", data.refund_ids); // Nessie TX IDs
    });


// ─────────────────────────────────────────────────────────────────────────────
// CREATE FX CORRIDOR  (cross-border, live rate lock)
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/corridors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        source_currency: "inr",
        target_currency: "usd",
        source_account_id: JORDAN,
        target_account_id: ALEX,
        amount_target: 4900,             // receive $49.00 USD
        description: "India → USA payment",
        lock_duration_minutes: 30,
        max_rate_drift_pct: 2.0,
    }),
})
    .then(r => r.json())
    .then(data => {
        console.log("Corridor:", data.id);
        console.log("Live rate:", data.rate_lock.rate);  // e.g. 0.01097
        console.log("Payer owes (INR cents):", data.amount_source_cents);
        console.log("Rate expires:", data.rate_lock.expires_at);
    });


// ─────────────────────────────────────────────────────────────────────────────
// REMIT THE CORRIDOR  (execute at locked rate)
// ─────────────────────────────────────────────────────────────────────────────
const CORRIDOR_ID = "crdr_YOUR_ID_HERE";
fetch(`${BASE}/v1/corridors/${CORRIDOR_ID}/remit`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
        console.log("Status:", data.status);               // "remitted"
        console.log("Nessie TX:", data.nessie_transfer_id);
    });


// ─────────────────────────────────────────────────────────────────────────────
// CREATE FX POOL  (multi-currency group collection)
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/fxpools/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        goal_amount_usd: 20000,          // $200 USD goal
        organizer_account_id: ALEX,
        payee_account_id: ALEX,
        description: "Global team expenses",
        deadline: "2026-03-10T00:00:00Z",
        max_rate_drift_pct: 3.0,
    }),
})
    .then(r => r.json())
    .then(data => {
        console.log("FX Pool:", data.id);
        console.log("Goal: $", data.goal_amount_usd / 100);
    });


// ─────────────────────────────────────────────────────────────────────────────
// CONTRIBUTE TO FX POOL  (in your own local currency)
// ─────────────────────────────────────────────────────────────────────────────
const FXPOOL_ID = "fxpool_YOUR_ID_HERE";
fetch(`${BASE}/v1/fxpools/${FXPOOL_ID}/contribute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        payer_account_id: JORDAN,
        currency: "eur",                 // inr | eur | gbp | usd | jpy ...
        amount_local: 4500,             // €45.00 → auto-converted to USD
    }),
})
    .then(r => r.json())
    .then(data => {
        console.log("Collected USD:", data.collected_usd / 100);
        console.log("Currencies so far:", data.currencies_collected);
        console.log("Status:", data.status);
    });


// ─────────────────────────────────────────────────────────────────────────────
// ANALYTICS
// ─────────────────────────────────────────────────────────────────────────────
fetch(`${BASE}/v1/analytics/`)
    .then(r => r.json())
    .then(console.log);


// ─────────────────────────────────────────────────────────────────────────────
// IDEMPOTENCY  (same key = same response, no duplicate)
// ─────────────────────────────────────────────────────────────────────────────
const makeCollect = (key) =>
    fetch(`${BASE}/v1/collects/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,           // ← Stripe-style idempotency
        },
        body: JSON.stringify({
            payee_account_id: ALEX,
            payer_account_id: JORDAN,
            amount: 2500,
            description: "Idempotency test",
            expires_at: "2026-03-10T00:00:00Z",
        }),
    }).then(async r => {
        const data = await r.json();
        console.log("Replayed?", r.headers.get("X-Idempotency-Replayed"), "| ID:", data.id);
    });

// Run twice — both print the same ID, second one shows "true"
makeCollect("my-unique-key-xyz").then(() => makeCollect("my-unique-key-xyz"));
