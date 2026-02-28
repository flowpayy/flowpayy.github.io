"""
Idempotency Key Middleware for FlowPay.

Stores request hashes keyed by Idempotency-Key header.
Same key + same endpoint = cached response (no duplicate resource created).
This is how Stripe implements it in production.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

# In-memory idempotency store: (key, path) -> response body
_idempotency_store = {}

class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Intercepts POST requests with an Idempotency-Key header.
    If the (key, path) pair has been seen before, returns the cached response.
    Otherwise, passes through and caches the response.
    """
    async def dispatch(self, request: Request, call_next):
        # Only apply to POST requests
        if request.method != "POST":
            return await call_next(request)
        
        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            return await call_next(request)
        
        cache_key = (idempotency_key, request.url.path)
        
        if cache_key in _idempotency_store:
            cached = _idempotency_store[cache_key]
            return Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers={
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                    "X-Idempotency-Replayed": "true"
                }
            )
        
        response = await call_next(request)
        
        # Cache successful POST responses (2xx)
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            _idempotency_store[cache_key] = {
                "body": body,
                "status_code": response.status_code
            }
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers) | {
                    "X-Idempotency-Key": idempotency_key,
                    "X-Idempotency-Replayed": "false"
                }
            )
        
        return response
