"""
demo.py — FlowPay API Demo Script
===================================

This script demonstrates all four key FlowPay scenarios using the Python SDK.
Run it after starting the backend: `uvicorn app.main:app --port 8000`

    cd hackillonni
    python demo.py

Requirements:
    pip install httpx
"""

import sys
import time
from flowpay import FlowPayClient, FlowPayError

# =============================================================================
# Demo account IDs (seeded via `cd backend && python seed.py`)
# =============================================================================
ALEX_ACC  = "69a268d595150878eaffa3ba"   # Freelancer / Payee
JORDAN_ACC = "69a268d595150878eaffa3bc"  # Client / Payer

BASE_URL = "http://localhost:8000"

# =============================================================================
# Helpers
# =============================================================================
def hr(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(label: str, value):
    print(f"  ✅  {label}: {value}")

def info(msg: str):
    print(f"  ℹ️   {msg}")

def warn(msg: str):
    print(f"  ⚠️   {msg}")

def money(cents: int, currency: str = "USD") -> str:
    return f"{currency} {cents / 100:.2f}"


# =============================================================================
# SCENARIO 1: Pull Collect (Receiver-Initiated Payment)
# =============================================================================
def scenario_1_collect(client: FlowPayClient):
    hr("Scenario 1 — Pull Payment (Collect)")
    info("Alex (freelancer) sends a payment request to Jordan (client).")
    info("Jordan sees it in their inbox and approves.")
    print()

    # ------------------------------------------------------------------
    # Step 1: Alex creates the payment request
    # ------------------------------------------------------------------
    collect = client.collects.create(
        payee_account_id=ALEX_ACC,
        payer_account_id=JORDAN_ACC,
        amount=4900,
        description="Logo design — Phase 1",
        expires_at="2026-03-10T00:00:00Z",
        idempotency_key=f"demo-collect-{int(time.time())}",
    )

    ok("Collect created", collect["id"])
    ok("Status", collect["status"])           # → pending
    ok("Amount", money(collect["amount"]))    # → USD 49.00
    ok("Description", collect["description"])

    # ------------------------------------------------------------------
    # Step 2: List Jordan's pending inbox
    # ------------------------------------------------------------------
    inbox = client.collects.list(payer_id=JORDAN_ACC, status="pending")
    ok("Jordan's pending inbox size", len(inbox))

    # ------------------------------------------------------------------
    # Step 3: Jordan approves → real Nessie transfer fires
    # ------------------------------------------------------------------
    info(f"\nJordan approves collect {collect['id']}...")
    approved = client.collects.approve(collect["id"])

    ok("New status", approved["status"])               # → approved
    ok("Nessie transfer ID", approved["nessie_transfer_id"])
    info("collect.approved webhook fired asynchronously.")

    # ------------------------------------------------------------------
    # Step 4: Try to approve again — should fail with proper error
    # ------------------------------------------------------------------
    print()
    info("Testing error handling: trying to approve again...")
    try:
        client.collects.approve(collect["id"])
    except FlowPayError as e:
        ok("Got expected error", f"[HTTP {e.status_code}] {e.error.get('code')}")

    return collect["id"]


# =============================================================================
# SCENARIO 2: Group Pool — Fully Funded
# =============================================================================
def scenario_2_pool_success(client: FlowPayClient):
    hr("Scenario 2 — Group Pool: Goal Reached, Auto-Settle")
    info("4 teammates chip in for a group dinner.")
    info("When the last contribution hits the goal, FlowPay auto-settles.")
    print()

    # Create the pool
    pool = client.pools.create(
        goal_amount=20000,          # $200.00
        organizer_account_id=ALEX_ACC,
        payee_account_id=ALEX_ACC,
        description="Team dinner at Au Cheval",
        deadline="2026-03-10T00:00:00Z",
    )
    ok("Pool created", pool["id"])
    ok("Goal", money(pool["goal_amount"]))
    ok("Status", pool["status"])  # → collecting

    # Contribute — 4 × $50 = $200 (hits goal, auto-settles)
    contributors = [
        (JORDAN_ACC, 5000),  # $50
        (JORDAN_ACC, 5000),
        (JORDAN_ACC, 5000),
        (JORDAN_ACC, 5000),  # Last one hits $200 → auto-settle fires
    ]
    for i, (payer, amount) in enumerate(contributors, 1):
        result = client.pools.contribute(pool["id"], payer_account_id=payer, amount=amount)
        collected = result["collected_amount"]
        status = result["status"]
        print(f"  💸  Contribution {i}/4: {money(amount)} — collected {money(collected)} — {status}")

    ok("Final pool status", result["status"])  # → funded
    info("pool.goal_reached webhook fired. Nessie settlement transfer sent.")


# =============================================================================
# SCENARIO 3: Group Pool — Auto-Refund (Cancelled)
# =============================================================================
def scenario_3_pool_refund(client: FlowPayClient):
    hr("Scenario 3 — Group Pool: Cancelled, Auto-Refund")
    info("Event cancelled before goal reached. Organizer cancels pool.")
    info("FlowPay issues a reverse Nessie transfer to every contributor.")
    print()

    # Create pool
    pool = client.pools.create(
        goal_amount=30000,  # $300.00 — won't be reached
        organizer_account_id=ALEX_ACC,
        payee_account_id=ALEX_ACC,
        description="Concert tickets — Coldplay",
        deadline="2026-03-10T00:00:00Z",
    )
    ok("Pool created", pool["id"])

    # Two partial contributions
    client.pools.contribute(pool["id"], payer_account_id=JORDAN_ACC, amount=5000)
    client.pools.contribute(pool["id"], payer_account_id=JORDAN_ACC, amount=7500)
    ok("Contributed", "$125.00 (partial — goal not reached)")

    # Cancel → auto-refund
    info("Organizer cancels pool...")
    cancelled = client.pools.cancel(pool["id"])
    ok("Pool status", cancelled["status"])  # → cancelled
    ok("Refunds issued", len(cancelled.get("refund_ids", [])))
    if cancelled.get("refund_ids"):
        for refund_id in cancelled["refund_ids"]:
            print(f"  🔁  Refund Nessie TX: {refund_id}")
    info("pool.cancelled webhook fired.")


# =============================================================================
# SCENARIO 4: FlowBridge — Cross-Border FX Corridor
# =============================================================================
def scenario_4_flowbridge(client: FlowPayClient):
    hr("Scenario 4 — FlowBridge: Cross-Border FX Corridor")
    info("Ravi (India) needs to pay a US freelancer $49.")
    info("FlowBridge fetches live INR→USD rate, locks it 30 min, remits.")
    print()

    # Create corridor with live rate lock
    info("Creating corridor: INR → USD (fetching live rate)...")
    corridor = client.corridors.create(
        source_currency="inr",
        target_currency="usd",
        source_account_id=JORDAN_ACC,
        target_account_id=ALEX_ACC,
        amount_target=4900,              # $49.00 USD
        description="Freelancer payment: India → USA",
        lock_duration_minutes=30,
        max_rate_drift_pct=2.0,
    )

    rate = corridor["rate_lock"]["rate"]
    source_amount = corridor["amount_source_cents"]
    ok("Corridor created", corridor["id"])
    ok("Live INR→USD rate", f"1 INR = {rate:.5f} USD")
    ok("Payer (Ravi) owes", f"₹{source_amount / 100:.2f}")
    ok("Payee receives", money(corridor["amount_target_cents"]))
    ok("Rate locked until", corridor["rate_lock"]["expires_at"])
    ok("Max drift allowed", f"{corridor['rate_lock']['max_drift_pct']}%")

    # Execute the transfer
    info("\nExecuting cross-border transfer at locked rate...")
    remitted = client.corridors.remit(corridor["id"])
    ok("Status", remitted["status"])              # → remitted
    ok("Nessie transfer ID", remitted["nessie_transfer_id"])
    info("corridor.settled webhook fired.")

    # ---------------------------------------------------------------
    # Bonus: FX Pool — Multi-Currency Group Collection
    # ---------------------------------------------------------------
    print()
    hr("Bonus — FlowBridge: Multi-Currency FX Pool")
    info("4 people in 4 countries split a $200 shared expense.")
    info("Each pays in their own currency. Auto-converts at live rates.")
    print()

    fxpool = client.fxpools.create(
        goal_amount_usd=20000,       # $200 USD goal
        organizer_account_id=ALEX_ACC,
        payee_account_id=ALEX_ACC,
        description="Global team expenses",
        deadline="2026-03-10T00:00:00Z",
        max_rate_drift_pct=3.0,
    )
    ok("FX Pool created", fxpool["id"])
    ok("Goal", money(fxpool["goal_amount_usd"]))

    # Each participant pays in their local currency
    contributions = [
        ("inr", 4100, "🇮🇳 Ravi",  "₹41.00"),
        ("eur", 4500, "🇩🇪 Emma",  "€45.00"),
        ("gbp", 3900, "🇬🇧 Liam",  "£39.00"),
        ("usd", 5000, "🇺🇸 Jordan","$50.00"),
    ]
    for currency, amount, name, display in contributions:
        result = client.fxpools.contribute(
            fxpool["id"],
            payer_account_id=JORDAN_ACC,
            currency=currency,
            amount_local=amount,
        )
        usd_collected = result["collected_usd"]
        print(f"  💱  {name} pays {display} → Pool: {money(usd_collected)} USD collected | status: {result['status']}")

    ok("Final status", result["status"])
    if result["status"] == "funded":
        info("All contributions met goal. Pool auto-settled to organizer.")
    info("Currencies collected: " + ", ".join(result.get("currencies_collected", [])).upper())


# =============================================================================
# ANALYTICS SNAPSHOT
# =============================================================================
def show_analytics(client: FlowPayClient):
    hr("Platform Analytics Snapshot")
    data = client.analytics.snapshot()
    c = data["collects"]
    p = data["pools"]
    r = data["recurring"]
    combined = data["combined"]

    print(f"  📊  Collects: {c['total']} total / {c['approved']} approved / {c['pending']} pending")
    print(f"  📊  Pools:    {p['total']} total / {p['funded']} funded / {p['cancelled']} cancelled")
    print(f"  📊  Recurring:{r['total']} active / {r['total_executions']} executions")
    print(f"  💰  Total Volume Settled: {money(combined['total_volume_settled_cents'])}")
    print(f"  💸  Total Refunded:       {money(p.get('volume_refunded_cents', 0))}")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print()
    print("⚡ FlowPay API Demo")
    print("The Payment Primitives Stripe Doesn't Have")
    print(f"API: {BASE_URL}")
    print()

    with FlowPayClient(BASE_URL) as client:
        # Health check
        health = client.health()
        ok("API Health", health["status"])

        # Run all scenarios
        scenario_1_collect(client)
        scenario_2_pool_success(client)
        scenario_3_pool_refund(client)
        scenario_4_flowbridge(client)

        # Platform analytics
        show_analytics(client)

    print()
    print("=" * 60)
    print("  ✅  All scenarios completed successfully.")
    print()
    print("  Open the interactive docs to explore further:")
    print(f"  → {BASE_URL}/docs")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
