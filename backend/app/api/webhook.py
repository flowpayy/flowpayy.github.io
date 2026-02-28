from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import uuid
import httpx

router = APIRouter(prefix="/v1/webhooks", tags=["Webhooks"])

# Simple memory storage for registered webhook URLs
registered_webhooks = []

class WebhookRegistration(BaseModel):
    url: str
    events: list[str] = ["*"]

@router.post("", status_code=status.HTTP_201_CREATED)
async def register_webhook(request: WebhookRegistration):
    webhook_id = f"webhook_{uuid.uuid4().hex[:8]}"
    hook = {
        "id": webhook_id,
        "url": request.url,
        "events": request.events
    }
    registered_webhooks.append(hook)
    return {"status": "success", "webhook": hook}
    
@router.get("")
async def list_webhooks():
    return {"webhooks": registered_webhooks}

# Internal utility to actually dispatch the event
async def dispatch_event(event_type: str, data: dict):
    # This fires off POST requests in the background
    payload = {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "object": "event",
        "type": event_type,
        "data": {"object": data}
    }
    
    async with httpx.AsyncClient() as client:
        for hook in registered_webhooks:
            if "*" in hook["events"] or event_type in hook["events"]:
                try:
                    # Non blocking logging 
                    await client.post(hook["url"], json=payload)
                except Exception as e:
                    print(f"Failed to trigger webhook {hook['url']}: {e}")
