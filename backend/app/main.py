from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from app.middleware.idempotency import IdempotencyMiddleware

app = FastAPI(
    title="FlowPay API",
    description="""
## The Payment Primitives Stripe Doesn't Have

FlowPay exposes three missing primitives for Western payment infrastructure:

- **Collect** — Receiver-initiated pull payment (UPI Collect-style)
- **Pool** — Group collection with deadline + auto-refund (Alipay AA Split-style)  
- **FlowBridge** — Cross-border FX corridors with rate locking (UPI x Wise-style)

Built at **HackIllinois 2026** · Stripe Track · Capital One Nessie

### Idempotency
All POST endpoints accept an `Idempotency-Key` header. Same key = cached response.

### Amounts
All monetary amounts are integers in **cents** (e.g. `4900` = `$49.00`).

### Error Format
```json
{ "detail": { "error": { "type": "...", "code": "...", "message": "..." } } }
```
""",
    version="1.0.0",
    contact={"name": "FlowPay API", "url": "http://localhost:3000"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Collects", "description": "Pull payment requests — receiver-initiated"},
        {"name": "Pools", "description": "Group collection with auto-refund"},
        {"name": "FlowBridge — Corridors", "description": "Cross-border FX corridors with rate locking"},
        {"name": "FlowBridge — FX Pools", "description": "Multi-currency group collection"},
        {"name": "Recurring Collects", "description": "Pre-authorized subscription pulls"},
        {"name": "Webhooks", "description": "Event-driven notifications"},
        {"name": "Analytics", "description": "Real-time platform metrics"},
    ]
)

# CORS — allow all localhost ports for hackathon demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Idempotency — Stripe-style duplicate-request prevention
app.add_middleware(IdempotencyMiddleware)

# Add X-FlowPay-Version header to all responses
@app.middleware("http")
async def add_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-FlowPay-Version"] = "2026-02-28"
    return response

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/v1/health", tags=["Health"], summary="API health check")
async def health_check():
    """Returns API health status. Use this to verify the server is running."""
    return {"status": "ok", "message": "FlowPay API is healthy and running.", "version": "1.0.0"}

from app.api import collect, pool, webhook
from app.api import recurring, analytics
from app.api import corridor, fxpool

app.include_router(collect.router)
app.include_router(pool.router)
app.include_router(webhook.router)
app.include_router(recurring.router)
app.include_router(analytics.router)
app.include_router(corridor.router)
app.include_router(fxpool.router)
