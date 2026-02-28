"""
FX (Foreign Exchange) Service for FlowBridge.

In production this would hit Stripe's FX rates API or a financial data provider.
For the hackathon demo, we use live rates from exchangerate.host (free, no key).
If the API is unavailable, we fall back to realistic hardcoded rates so the demo never breaks.
"""
import httpx
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

# Fallback rates against USD (as of Feb 2026 approximate)
FALLBACK_RATES_TO_USD: Dict[str, float] = {
    "usd": 1.0,
    "eur": 1.08,
    "gbp": 1.27,
    "inr": 0.01202,
    "jpy": 0.0066,
    "cad": 0.74,
    "aud": 0.64,
    "cny": 0.138,
    "sgd": 0.74,
    "mxn": 0.051,
}

# In-memory locked rate store: rate_lock_id -> {rate, expires_at, source, target, ...}
rate_lock_store: Dict[str, dict] = {}

async def get_live_rate(source_currency: str, target_currency: str) -> float:
    """Fetch live exchange rate. Falls back to hardcoded rates if API unavailable."""
    src = source_currency.lower()
    tgt = target_currency.lower()
    if src == tgt:
        return 1.0
    
    try:
        # Free, no-key public API for live FX rates
        url = f"https://open.er-api.com/v6/latest/{src.upper()}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get(tgt.upper())
                if rate:
                    return float(rate)
    except Exception:
        pass
    
    # Fallback: cross-rate calculation via USD
    src_to_usd = FALLBACK_RATES_TO_USD.get(src, 1.0)
    tgt_to_usd = FALLBACK_RATES_TO_USD.get(tgt, 1.0)
    return src_to_usd / tgt_to_usd

async def lock_rate(
    source_currency: str,
    target_currency: str,
    amount_target: int,  # in target currency cents
    lock_duration_minutes: int = 30,
    max_drift_pct: float = 2.0
) -> dict:
    """
    Lock a FX rate for a given currency pair and target amount.
    Returns the locked rate, equivalent source amount, and expiry.
    """
    rate = await get_live_rate(source_currency, target_currency)
    # rate is: 1 source_currency = `rate` target_currency
    # We need: How much source for amount_target?
    # amount_target_decimal = amount_target / 100
    # source_decimal = amount_target_decimal / rate
    # source_cents = int(source_decimal * 100)
    if rate == 0:
        rate = 1.0
    
    amount_target_decimal = amount_target / 100
    source_decimal = amount_target_decimal / rate
    amount_source_cents = int(source_decimal * 100)
    
    lock_id = f"rate_{uuid.uuid4().hex[:12]}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=lock_duration_minutes)
    
    lock = {
        "id": lock_id,
        "object": "rate_lock",
        "source_currency": source_currency.lower(),
        "target_currency": target_currency.lower(),
        "rate": rate,  # 1 source = rate target
        "amount_target_cents": amount_target,
        "amount_source_cents": amount_source_cents,
        "max_drift_pct": max_drift_pct,
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "active",  # active, used, expired, drifted
    }
    rate_lock_store[lock_id] = lock
    return lock

async def check_drift(lock_id: str) -> dict:
    """Check if rate has drifted beyond tolerance since locking."""
    lock = rate_lock_store.get(lock_id)
    if not lock:
        return {"drifted": False, "error": "Lock not found"}
    
    current_rate = await get_live_rate(lock["source_currency"], lock["target_currency"])
    locked_rate = lock["rate"]
    drift_pct = abs((current_rate - locked_rate) / locked_rate) * 100
    drifted = drift_pct > lock["max_drift_pct"]
    
    return {
        "lock_id": lock_id,
        "locked_rate": locked_rate,
        "current_rate": current_rate,
        "drift_pct": round(drift_pct, 4),
        "max_drift_pct": lock["max_drift_pct"],
        "drifted": drifted,
    }
