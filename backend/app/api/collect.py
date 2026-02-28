from fastapi import APIRouter, HTTPException, status
from typing import List
from datetime import datetime, timezone
import uuid
from app.models.schemas import CollectCreateRequest, CollectResponse, ErrorResponse
from app.api.webhook import dispatch_event
from app.services.nessie import transfer, get_balance

router = APIRouter(prefix="/v1/collects", tags=["Collects"])

# In-memory database for prototyping
fake_collect_db = {}

@router.post("", response_model=CollectResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CollectResponse, status_code=status.HTTP_201_CREATED)
async def create_collect(request: CollectCreateRequest):
    collect_id = f"clct_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    collect = CollectResponse(
        id=collect_id,
        status="pending",
        amount=request.amount,
        currency=request.currency,
        description=request.description,
        payee_account_id=request.payee_account_id,
        payer_account_id=request.payer_account_id,
        expires_at=request.expires_at,
        created_at=now,
        metadata=request.metadata
    )
    fake_collect_db[collect_id] = collect
    return collect

@router.get("/{collect_id}", response_model=CollectResponse)
async def get_collect(collect_id: str):
    collect = fake_collect_db.get(collect_id)
    if not collect:
        raise HTTPException(status_code=404, detail="Collect request not found")
    return collect

@router.get("", response_model=List[CollectResponse], summary="List payment requests",
    description="Filter by payer or payee. Supports pagination and status filtering.")
@router.get("/", response_model=List[CollectResponse], include_in_schema=False)
async def list_collects(
    payer_id: str = None,
    payee_id: str = None,
    status: str = None,          # pending | approved | declined | expired
    limit: int = 20,
    offset: int = 0
):
    results = []
    for collect in fake_collect_db.values():
        match = False
        if payer_id and collect.payer_account_id == payer_id:
            match = True
        elif payee_id and collect.payee_account_id == payee_id:
            match = True
        elif not payer_id and not payee_id:
            match = True
        if match and status and collect.status != status:
            match = False
        if match:
            results.append(collect)
    # Pagination
    total = len(results)
    paginated = results[offset: offset + limit]
    return paginated

@router.post("/{collect_id}/approve", response_model=CollectResponse)
async def approve_collect(collect_id: str):
    collect = fake_collect_db.get(collect_id)
    if not collect:
        raise HTTPException(status_code=404, detail="Collect request not found")
    if collect.status != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot approve collect in {collect.status} status"
        )
    
    # 1. Check expiration
    if datetime.now(timezone.utc) > collect.expires_at:
        collect.status = "expired"
        await dispatch_event("collect.expired", collect.dict())
        raise HTTPException(
            status_code=410,
            detail={
                "error": {
                    "type": "invalid_request_error", "code": "collect_expired",
                    "message": f"This collect request expired on {collect.expires_at}.",
                    "expired_at": collect.expires_at.isoformat()
                }
            }
        )

    # 2. Check Nessie balance
    try:
        balance = await get_balance(collect.payer_account_id)
        if balance < collect.amount:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": {
                        "type": "payment_error", "code": "insufficient_funds",
                        "message": f"Payer account balance is insufficient for this collect.",
                        "param": "payer_account_id",
                        "nessie_balance": balance,
                        "required_amount": collect.amount
                    }
                }
            )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=400, detail="Failed to fetch payer balance from Nessie")

    # 3. Execute Transfer
    try:
        transfer_id = await transfer(
            payer_account_id=collect.payer_account_id,
            payee_account_id=collect.payee_account_id,
            amount=collect.amount,
            description=f"FlowPay collect {collect.id}"
        )
    except Exception as e:
         raise HTTPException(status_code=500, detail="Nessie transfer failed")

    collect.status = "approved"
    collect.approved_at = datetime.now(timezone.utc)
    collect.nessie_transfer_id = transfer_id
    
    await dispatch_event("collect.approved", collect.dict())
    
    return collect

@router.post("/{collect_id}/decline", response_model=CollectResponse)
async def decline_collect(collect_id: str, reason: str = None):
    collect = fake_collect_db.get(collect_id)
    if not collect:
        raise HTTPException(status_code=404, detail="Collect request not found")
    if collect.status != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot decline collect in {collect.status} status"
        )
        
    collect.status = "declined"
    collect.declined_at = datetime.now(timezone.utc)
    await dispatch_event("collect.declined", collect.dict())
    
    return collect
