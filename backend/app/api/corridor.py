"""
FlowBridge Corridor API — Cross-Border Pull Payments

A Corridor defines a programmable FX route between two currency/account pairs.
Once created, you lock the rate and remit within the lock window.

This is the primitive that doesn't exist in Stripe or Capital One today:
receiver-initiated, FX-rate-locked, cross-border payment request.

Inspired by: UPI cross-border (NPCI linking India <-> Singapore/UAE),
             Wise business API (consumer-only), GPI Swift improvements.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from app.services.fx import lock_rate, check_drift, get_live_rate, rate_lock_store
from app.services.nessie import transfer
from app.api.webhook import dispatch_event

router = APIRouter(prefix="/v1/corridors", tags=["FlowBridge — Corridors"])

corridor_db = {}

class CorridorCreateRequest(BaseModel):
    source_currency: str              # e.g. "inr" — payer's currency
    target_currency: str              # e.g. "usd" — payee's currency
    source_account_id: str            # Nessie account of payer
    target_account_id: str            # Nessie account of payee
    amount_target: int                # Amount PAYEE wants, in target currency cents
    description: str
    lock_duration_minutes: int = 30   # How long the rate is locked
    max_rate_drift_pct: float = 2.0   # Auto-cancel if rate moves more than this %
    metadata: Optional[dict] = None

@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_corridor(request: CorridorCreateRequest):
    """
    Create a cross-border payment corridor with a locked FX rate.
    The payee defines how much they want in their currency.
    FlowBridge quotes the payer's equivalent amount in their currency
    and locks the rate for `lock_duration_minutes`.

    No equivalent exists in Stripe, Capital One, or any Western API today.
    """
    rate_lock = await lock_rate(
        source_currency=request.source_currency,
        target_currency=request.target_currency,
        amount_target=request.amount_target,
        lock_duration_minutes=request.lock_duration_minutes,
        max_drift_pct=request.max_rate_drift_pct
    )

    corridor_id = f"crdr_{uuid.uuid4().hex[:12]}"
    corridor = {
        "id": corridor_id,
        "object": "corridor",
        "status": "rate_locked",  # rate_locked → remitted | expired | cancelled | drift_cancelled
        "description": request.description,
        "source_currency": request.source_currency.lower(),
        "target_currency": request.target_currency.lower(),
        "source_account_id": request.source_account_id,
        "target_account_id": request.target_account_id,
        "amount_target_cents": request.amount_target,
        "amount_source_cents": rate_lock["amount_source_cents"],
        "rate_lock": rate_lock,
        "nessie_transfer_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "remitted_at": None,
        "metadata": request.metadata,
    }
    corridor_db[corridor_id] = corridor
    await dispatch_event("corridor.rate_locked", corridor)
    return corridor

@router.get("/{corridor_id}")
async def get_corridor(corridor_id: str):
    corridor = corridor_db.get(corridor_id)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found")
    return corridor

@router.get("/{corridor_id}/rate-check")
async def check_corridor_rate(corridor_id: str):
    """Check live drift on a corridor's locked rate before remitting."""
    corridor = corridor_db.get(corridor_id)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found")
    drift_info = await check_drift(corridor["rate_lock"]["id"])
    return drift_info

@router.post("/{corridor_id}/remit")
async def remit_corridor(corridor_id: str):
    """
    Execute the cross-border transfer at the locked FX rate.
    Validates: rate lock not expired, drift within tolerance.
    Then fires two Nessie transfers (simulating source debit + target credit).
    """
    corridor = corridor_db.get(corridor_id)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found")
    if corridor["status"] != "rate_locked":
        raise HTTPException(status_code=400, detail=f"Cannot remit corridor in {corridor['status']} status")

    # Check expiry
    expires_at = datetime.fromisoformat(corridor["rate_lock"]["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        corridor["status"] = "expired"
        await dispatch_event("corridor.rate_expired", corridor)
        raise HTTPException(
            status_code=410,
            detail={
                "error": {
                    "type": "corridor_error",
                    "code": "rate_lock_expired",
                    "message": f"The FX rate lock expired at {corridor['rate_lock']['expires_at']}. Create a new corridor.",
                    "expired_at": corridor["rate_lock"]["expires_at"]
                }
            }
        )

    # Check rate drift
    drift = await check_drift(corridor["rate_lock"]["id"])
    if drift["drifted"]:
        corridor["status"] = "drift_cancelled"
        await dispatch_event("corridor.drift_cancelled", {**corridor, "drift_info": drift})
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "type": "corridor_error",
                    "code": "rate_drift_exceeded",
                    "message": f"FX rate moved {drift['drift_pct']:.2f}% (max allowed: {drift['max_drift_pct']}%). Corridor auto-cancelled.",
                    "locked_rate": drift["locked_rate"],
                    "current_rate": drift["current_rate"],
                    "drift_pct": drift["drift_pct"],
                }
            }
        )

    # Execute Nessie transfers — source debit
    try:
        txn_id = await transfer(
            payer_account_id=corridor["source_account_id"],
            payee_account_id=corridor["target_account_id"],
            amount=corridor["amount_source_cents"],  # debit in source currency units
            description=f"FlowBridge corridor {corridor_id} — {corridor['source_currency'].upper()} → {corridor['target_currency'].upper()}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Nessie transfer failed")

    corridor["status"] = "remitted"
    corridor["nessie_transfer_id"] = txn_id
    corridor["remitted_at"] = datetime.now(timezone.utc).isoformat()
    corridor["rate_lock"]["status"] = "used"

    await dispatch_event("corridor.settled", corridor)
    return corridor

@router.get("")
@router.get("/")
async def list_corridors():
    return list(corridor_db.values())
