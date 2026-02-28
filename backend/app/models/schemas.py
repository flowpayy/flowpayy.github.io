from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CollectCreateRequest(BaseModel):
    payee_account_id: str
    payer_account_id: str
    amount: int = Field(..., description="Amount in cents")
    currency: str = "usd"
    description: str
    expires_at: datetime
    metadata: Optional[Dict[str, Any]] = None

class CollectResponse(BaseModel):
    id: str
    object: str = "collect"
    status: str # pending, approved, declined, expired
    amount: int
    currency: str
    description: str
    payee_account_id: str
    payer_account_id: str
    nessie_transfer_id: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    approved_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class PoolCreateRequest(BaseModel):
    goal_amount: int = Field(..., description="Goal in cents")
    currency: str = "usd"
    description: str
    organizer_account_id: str
    payee_account_id: str
    deadline: datetime
    on_deadline_miss: str = "refund_all" # or settle_partial

class PoolResponse(BaseModel):
    id: str
    object: str = "pool"
    status: str # collecting, funded, cancelled, expired, expired_refunded
    goal_amount: int
    collected_amount: int = 0
    currency: str
    description: str
    organizer_account_id: str
    payee_account_id: str
    participant_count: int = 0
    contributions_count: int = 0
    deadline: datetime
    on_deadline_miss: str
    created_at: datetime
    funded_at: Optional[datetime] = None
    nessie_transfer_ids: List[str] = []
    refund_ids: Optional[List[str]] = None

class PoolContributeRequest(BaseModel):
    payer_account_id: str
    amount: int = Field(..., description="Amount in cents")
    
class ErrorDetail(BaseModel):
    type: str
    code: str
    message: str
    param: Optional[str] = None
    nessie_balance: Optional[int] = None
    required_amount: Optional[int] = None
    expired_at: Optional[datetime] = None
    refunded: Optional[int] = None
    refund_ids: Optional[List[str]] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
