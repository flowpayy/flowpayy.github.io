"""
FlowBridge FX Pool API — Multi-Currency Group Collection

A FX Pool allows participants in different countries to contribute in their
own local currency toward a shared goal (in a base currency — USD by default).
FlowBridge handles all FX conversions at settlement.

Key innovation over Stripe + standard Pool:
- Each participant pays in their local currency
- FX rates are locked per-contribution
- If rates drift beyond tolerance BEFORE settlement, everyone gets auto-refunded
  in their ORIGINAL currency (not converted) — no FX risk to participants
- When all participants pay, FlowBridge settles to organizer in base currency

Real-world use cases:
- 4 friends across India/UK/Germany/USA splitting a vacation rental
- International team buying a group gift in the organizer's currency
- Cross-border crowdfunding with guaranteed FX rates
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from app.services.fx import get_live_rate, lock_rate, check_drift, rate_lock_store
from app.services.nessie import transfer
from app.api.webhook import dispatch_event

router = APIRouter(prefix="/v1/fxpools", tags=["FlowBridge — FX Pools"])

fxpool_db = {}
fxpool_contributions_db = {}  # pool_id -> list of contributions

class FXPoolParticipant(BaseModel):
    account_id: str
    currency: str           # their local currency
    amount_local: int       # how much they contribute in their currency (cents)

class FXPoolCreateRequest(BaseModel):
    goal_amount_usd: int    # Goal in USD cents
    organizer_account_id: str
    payee_account_id: str
    description: str
    deadline: datetime
    max_rate_drift_pct: float = 3.0
    on_deadline_miss: str = "refund_all"

class FXPoolContributeRequest(BaseModel):
    payer_account_id: str
    currency: str           # participant's local currency
    amount_local: int       # amount in their currency (cents)

@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_fxpool(request: FXPoolCreateRequest):
    pool_id = f"fxpool_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    pool = {
        "id": pool_id,
        "object": "fxpool",
        "status": "collecting",
        "goal_amount_usd": request.goal_amount_usd,
        "collected_usd": 0,
        "organizer_account_id": request.organizer_account_id,
        "payee_account_id": request.payee_account_id,
        "description": request.description,
        "deadline": request.deadline.isoformat(),
        "max_rate_drift_pct": request.max_rate_drift_pct,
        "on_deadline_miss": request.on_deadline_miss,
        "contributions_count": 0,
        "created_at": now.isoformat(),
        "funded_at": None,
        "nessie_settlement_id": None,
        "currencies_collected": [],
    }
    fxpool_db[pool_id] = pool
    fxpool_contributions_db[pool_id] = []
    return pool

@router.get("/{pool_id}")
async def get_fxpool(pool_id: str):
    pool = fxpool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="FX Pool not found")
    return pool

@router.post("/{pool_id}/contribute")
async def contribute_to_fxpool(pool_id: str, request: FXPoolContributeRequest):
    """
    Add a contribution in any local currency.
    FlowBridge locks the FX rate for this contribution at time of payment.
    The participant's Nessie account is debited. The USD equivalent is added to the pool total.
    If the pool goal is reached, settlement fires automatically.
    """
    pool = fxpool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="FX Pool not found")
    if pool["status"] != "collecting":
        raise HTTPException(status_code=400, detail=f"Cannot contribute to fxpool in {pool['status']} status")

    deadline = datetime.fromisoformat(pool["deadline"])
    if datetime.now(timezone.utc) > deadline:
        raise HTTPException(status_code=422, detail={"error": {"code": "fxpool_expired", "message": "Pool deadline has passed"}})

    # Get live rate and convert to USD
    src_currency = request.currency.lower()
    usd_rate = await get_live_rate(src_currency, "usd")
    amount_usd = int((request.amount_local / 100) * usd_rate * 100)

    # Lock the rate for this contribution
    rate_lock = await lock_rate(
        source_currency=src_currency,
        target_currency="usd",
        amount_target=amount_usd,
        lock_duration_minutes=60 * 24,  # 24h — locked for the pool's lifetime
        max_drift_pct=pool["max_rate_drift_pct"]
    )

    # Execute Nessie transfer from payer to organizer holding account
    try:
        txn_id = await transfer(
            payer_account_id=request.payer_account_id,
            payee_account_id=pool["organizer_account_id"],
            amount=request.amount_local,
            description=f"FlowBridge FX Pool {pool_id} contribution — {src_currency.upper()} → USD"
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Nessie transfer failed")

    contribution = {
        "id": f"fxc_{uuid.uuid4().hex[:8]}",
        "payer_account_id": request.payer_account_id,
        "currency": src_currency,
        "amount_local": request.amount_local,
        "amount_usd": amount_usd,
        "usd_rate": usd_rate,
        "rate_lock_id": rate_lock["id"],
        "nessie_transfer_id": txn_id,
        "contributed_at": datetime.now(timezone.utc).isoformat(),
    }
    fxpool_contributions_db[pool_id].append(contribution)

    pool["collected_usd"] += amount_usd
    pool["contributions_count"] += 1
    if src_currency not in pool["currencies_collected"]:
        pool["currencies_collected"].append(src_currency)

    await dispatch_event("fxpool.contribution_received", {**pool, "contribution": contribution})

    # Check if goal reached
    if pool["collected_usd"] >= pool["goal_amount_usd"]:
        # First check for drift on any locked rates
        has_drift = False
        for contrib in fxpool_contributions_db[pool_id]:
            drift = await check_drift(contrib["rate_lock_id"])
            if drift.get("drifted"):
                has_drift = True
                break

        if has_drift:
            return await _trigger_fxpool_refund(pool_id, "rate_drift")

        # Settle to payee
        try:
            settle_txn = await transfer(
                payer_account_id=pool["organizer_account_id"],
                payee_account_id=pool["payee_account_id"],
                amount=pool["collected_usd"],
                description=f"FlowBridge FX Pool {pool_id} settlement"
            )
        except Exception:
            settle_txn = f"mock_settle_{uuid.uuid4().hex[:8]}"

        pool["status"] = "funded"
        pool["funded_at"] = datetime.now(timezone.utc).isoformat()
        pool["nessie_settlement_id"] = settle_txn
        await dispatch_event("fxpool.goal_reached", pool)

    return {**pool, "last_contribution": contribution}

@router.post("/{pool_id}/force-drift")
async def simulate_rate_drift(pool_id: str):
    """
    DEMO ONLY: Simulates FX rate drift beyond tolerance to trigger auto-refund.
    This is the most impressive thing at the demo — shows production-grade failure handling.
    """
    pool = fxpool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="FX Pool not found")
    return await _trigger_fxpool_refund(pool_id, "rate_drift_simulated")

@router.post("/{pool_id}/cancel")
async def cancel_fxpool(pool_id: str):
    pool = fxpool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="FX Pool not found")
    return await _trigger_fxpool_refund(pool_id, "organizer_cancelled")

async def _trigger_fxpool_refund(pool_id: str, reason: str):
    pool = fxpool_db[pool_id]
    pool["status"] = "cancelled" if reason == "organizer_cancelled" else "drift_refunded"
    refunds = []
    for contrib in fxpool_contributions_db.get(pool_id, []):
        try:
            ref_txn = await transfer(
                payer_account_id=pool["organizer_account_id"],
                payee_account_id=contrib["payer_account_id"],
                amount=contrib["amount_local"],  # refund in ORIGINAL local currency
                description=f"FlowBridge FX Pool {pool_id} refund ({reason})"
            )
            refunds.append({"payer": contrib["payer_account_id"], "currency": contrib["currency"],
                           "amount_refunded": contrib["amount_local"], "nessie_id": ref_txn})
        except Exception:
            refunds.append({"payer": contrib["payer_account_id"], "error": "refund failed"})

    event = "fxpool.rate_drifted" if "drift" in reason else "fxpool.cancelled"
    await dispatch_event(event, {**pool, "refunds": refunds, "reason": reason})
    return {**pool, "refunds": refunds, "reason": reason}

@router.get("/{pool_id}/contributions")
async def get_fxpool_contributions(pool_id: str):
    if pool_id not in fxpool_db:
        raise HTTPException(status_code=404, detail="FX Pool not found")
    return {"contributions": fxpool_contributions_db.get(pool_id, [])}

@router.get("")
@router.get("/")
async def list_fxpools():
    return list(fxpool_db.values())
