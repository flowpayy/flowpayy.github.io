from fastapi import APIRouter, HTTPException, status
from typing import List
from datetime import datetime, timezone
import uuid
from app.models.schemas import PoolCreateRequest, PoolResponse, PoolContributeRequest, ErrorResponse
from app.api.webhook import dispatch_event
from app.services.nessie import transfer, get_balance

router = APIRouter(prefix="/v1/pools", tags=["Pools"])

# In-memory DB
fake_pool_db = {}
fake_contributions_db = {} # pool_id -> List[dict]

@router.post("", response_model=PoolResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool(request: PoolCreateRequest):
    pool_id = f"pool_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    pool = PoolResponse(
        id=pool_id,
        status="collecting",
        goal_amount=request.goal_amount,
        currency=request.currency,
        description=request.description,
        organizer_account_id=request.organizer_account_id,
        payee_account_id=request.payee_account_id,
        deadline=request.deadline,
        on_deadline_miss=request.on_deadline_miss,
        created_at=now
    )
    fake_pool_db[pool_id] = pool
    fake_contributions_db[pool_id] = []
    
    return pool

@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(pool_id: str):
    pool = fake_pool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool

@router.post("/{pool_id}/contribute", response_model=PoolResponse)
async def contribute_to_pool(pool_id: str, request: PoolContributeRequest):
    pool = fake_pool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    
    if pool.status == "funded":
        raise HTTPException(
            status_code=409,
            detail=f"Pool {pool_id} reached its goal and has been settled. No further contributions accepted."
        )
    # 1. Check expiration
    if datetime.now(timezone.utc) > pool.deadline:
         raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "type": "pool_error",
                    "code": "pool_expired",
                    "message": "Pool expired without reaching goal."
                }
            }
        )

    # 2. Check Nessie balance
    try:
        balance = await get_balance(request.payer_account_id)
        if balance < request.amount:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": {
                        "type": "payment_error", "code": "insufficient_funds",
                        "message": f"Payer account balance is insufficient for this contribution.",
                        "param": "payer_account_id",
                        "nessie_balance": balance,
                        "required_amount": request.amount
                    }
                }
            )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=400, detail="Failed to fetch payer balance from Nessie")
        
    # 3. Execute Transfer to Pool Holding (Mocked as organizer account for now, since we don't have true escrows)
    try:
        transfer_id = await transfer(
            payer_account_id=request.payer_account_id,
            payee_account_id=pool.organizer_account_id,
            amount=request.amount,
            description=f"FlowPay pool contribution {pool.id}"
        )
    except Exception as e:
         raise HTTPException(status_code=500, detail="Nessie transfer failed")
    
    fake_contributions_db[pool_id].append({
        "payer_account_id": request.payer_account_id,
        "amount": request.amount,
        "nessie_transfer_id": transfer_id 
    })
    
    pool.collected_amount += request.amount
    pool.participant_count = len(set([c["payer_account_id"] for c in fake_contributions_db[pool_id]]))
    pool.contributions_count += 1
    
    # Check if goal reached
    if pool.collected_amount >= pool.goal_amount:
        pool.status = "funded"
        pool.funded_at = datetime.now(timezone.utc)
        
        # 4. Execute settlement transfer from holding to final payee
        try:
             settle_txn = await transfer(
                payer_account_id=pool.organizer_account_id,
                payee_account_id=pool.payee_account_id,
                amount=pool.collected_amount,
                description=f"FlowPay pool settlement {pool.id}"
            )
             pool.nessie_transfer_ids.append(settle_txn)
        except Exception:
             pass # In a real system, queue this for retry
        
        await dispatch_event("pool.goal_reached", pool.dict())
    else:
        await dispatch_event("pool.contribution_received", pool.dict())
        
        
    return pool

@router.post("/{pool_id}/cancel", response_model=PoolResponse)
async def cancel_pool(pool_id: str):
    pool = fake_pool_db.get(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
        
    if pool.status != "collecting":
         raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel pool in {pool.status} status"
        )
         
    pool.status = "cancelled"
    
    # Refund loop using Nessie
    pool.refund_ids = []
    for c in fake_contributions_db[pool_id]:
        try:
            # Create reverse transfer (refund)
            refund_txn = await transfer(
                payer_account_id=pool.organizer_account_id,
                payee_account_id=c["payer_account_id"],
                amount=c["amount"],
                description=f"FlowPay refund for pool {pool.id}"
            )
            pool.refund_ids.append(refund_txn)
        except Exception as e:
            print(f"Failed to refund {c['payer_account_id']}: {e}")
            pool.refund_ids.append(f"failed_ref_{uuid.uuid4().hex[:6]}")
        
    await dispatch_event("pool.cancelled", pool.dict())
    return pool

@router.get("/{pool_id}/contributions")
async def get_pool_contributions(pool_id: str):
    if pool_id not in fake_pool_db:
         raise HTTPException(status_code=404, detail="Pool not found")
    return {"contributions": fake_contributions_db[pool_id]}
