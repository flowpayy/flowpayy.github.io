from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from app.api.webhook import dispatch_event
from app.services.nessie import transfer, get_balance
from app.api.collect import fake_collect_db
from app.models.schemas import CollectCreateRequest, CollectResponse

router = APIRouter(prefix="/v1/recurring", tags=["Recurring Collects"])

# In-memory store  
recurring_db = {}

class RecurringCollectRequest(BaseModel):
    payee_account_id: str
    payer_account_id: str
    amount: int
    currency: str = "usd"
    description: str
    interval: str = "monthly"  # daily, weekly, monthly, yearly
    max_occurrences: Optional[int] = None  # None = indefinite
    pre_approved: bool = True   # payer pre-authorized recurring pulls

class RecurringCollectResponse(BaseModel):
    id: str
    object: str = "recurring_collect"
    status: str  # active, paused, cancelled, completed
    payee_account_id: str
    payer_account_id: str
    amount: int
    currency: str
    description: str
    interval: str
    occurrences_count: int = 0
    max_occurrences: Optional[int]
    pre_approved: bool
    created_at: datetime
    next_collect_at: Optional[datetime] = None

@router.post("", response_model=RecurringCollectResponse, status_code=201)
@router.post("/", response_model=RecurringCollectResponse, status_code=201)
async def create_recurring_collect(request: RecurringCollectRequest):
    """
    Create a pre-authorized recurring pull payment.
    The payer pre-approves, and FlowPay automatically executes 
    collects at each interval without requiring repeated approvals.
    This is the 'subscription pull' primitive — more flexible than 
    cards-on-file, with full audit trail per interval.
    """
    recurring_id = f"rec_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    rec = RecurringCollectResponse(
        id=recurring_id,
        status="active",
        payee_account_id=request.payee_account_id,
        payer_account_id=request.payer_account_id,
        amount=request.amount,
        currency=request.currency,
        description=request.description,
        interval=request.interval,
        max_occurrences=request.max_occurrences,
        pre_approved=request.pre_approved,
        created_at=now,
        next_collect_at=now  # Would normally be now + interval
    )
    recurring_db[recurring_id] = rec
    return rec

@router.post("/{recurring_id}/pause", response_model=RecurringCollectResponse)
async def pause_recurring(recurring_id: str):
    rec = recurring_db.get(recurring_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recurring collect not found")
    rec.status = "paused"
    return rec

@router.post("/{recurring_id}/cancel", response_model=RecurringCollectResponse)
async def cancel_recurring(recurring_id: str):
    rec = recurring_db.get(recurring_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recurring collect not found")
    rec.status = "cancelled"
    await dispatch_event("recurring.cancelled", rec.dict())
    return rec

@router.post("/{recurring_id}/trigger", response_model=dict)
async def trigger_recurring_collect(recurring_id: str):
    """
    Manually trigger one occurrence of a recurring collect.
    In production this would be called by an internal scheduler (Celery/cron).
    Demonstrated here manually for the hackathon demo.
    """
    rec = recurring_db.get(recurring_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recurring collect not found")
    if rec.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot trigger recurring collect in {rec.status} status")
    if rec.max_occurrences and rec.occurrences_count >= rec.max_occurrences:
        rec.status = "completed"
        return {"status": "completed", "message": "Max occurrences reached"}
    
    try:
        transfer_id = await transfer(
            payer_account_id=rec.payer_account_id,
            payee_account_id=rec.payee_account_id,
            amount=rec.amount,
            description=f"FlowPay recurring {rec.id} — occurrence {rec.occurrences_count + 1}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Transfer failed")
    
    rec.occurrences_count += 1
    await dispatch_event("recurring.collect_executed", {**rec.dict(), "nessie_transfer_id": transfer_id})
    
    return {
        "recurring_id": rec.id,
        "occurrence": rec.occurrences_count,
        "nessie_transfer_id": transfer_id,
        "amount": rec.amount,
        "status": "executed"
    }

@router.get("", response_model=list)
@router.get("/", response_model=list)
async def list_recurring(payee_id: str = None, payer_id: str = None):
    results = []
    for rec in recurring_db.values():
        if payee_id and rec.payee_account_id == payee_id:
            results.append(rec)
        elif payer_id and rec.payer_account_id == payer_id:
            results.append(rec)
    return results
