"""
flowpay.py — Official Python SDK for the FlowPay API
=====================================================

Usage:
    from flowpay import FlowPayClient, FlowPayError

    client = FlowPayClient(base_url="http://localhost:8000")

    # Create a pull payment request
    collect = client.collects.create(
        payee_account_id="ACC_ALEX",
        payer_account_id="ACC_JORDAN",
        amount=4900,
        description="Logo design",
        expires_at="2026-03-10T00:00:00Z"
    )

    # Approve it
    approved = client.collects.approve(collect["id"])
    print(f"Nessie TX: {approved['nessie_transfer_id']}")

Install requirements:
    pip install httpx
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime


class FlowPayError(Exception):
    """Raised when the FlowPay API returns an error response."""
    def __init__(self, status_code: int, error: Dict):
        self.status_code = status_code
        self.error = error
        code = error.get("code", "unknown_error")
        msg = error.get("message", str(error))
        super().__init__(f"[HTTP {status_code}] {code}: {msg}")


class _Resource:
    def __init__(self, client: "FlowPayClient"):
        self._client = client

    def _req(self, method: str, path: str, **kwargs) -> Dict:
        return self._client._request(method, path, **kwargs)


class CollectsResource(_Resource):
    """
    Pull payment requests — receiver-initiated.
    Payee creates. Payer approves or declines.
    """
    def create(
        self,
        payee_account_id: str,
        payer_account_id: str,
        amount: int,
        description: str,
        expires_at: str,
        currency: str = "usd",
        metadata: Optional[Dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Create a pull payment request.
        Amount is in cents (e.g. 4900 = $49.00).
        """
        return self._req("POST", "/v1/collects/", json={
            "payee_account_id": payee_account_id,
            "payer_account_id": payer_account_id,
            "amount": amount,
            "description": description,
            "expires_at": expires_at,
            "currency": currency,
            "metadata": metadata,
        }, idempotency_key=idempotency_key)

    def get(self, collect_id: str) -> Dict:
        """Retrieve a specific collect request."""
        return self._req("GET", f"/v1/collects/{collect_id}")

    def list(
        self,
        payer_id: Optional[str] = None,
        payee_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """
        List collect requests.
        Filter by payer_id, payee_id, or status (pending|approved|declined|expired).
        """
        params = {"limit": limit, "offset": offset}
        if payer_id: params["payer_id"] = payer_id
        if payee_id: params["payee_id"] = payee_id
        if status: params["status"] = status
        return self._req("GET", "/v1/collects/", params=params)

    def approve(self, collect_id: str) -> Dict:
        """
        Approve a collect request.
        FlowPay checks payer balance, fires a Nessie transfer, and
        returns the nessie_transfer_id.
        """
        return self._req("POST", f"/v1/collects/{collect_id}/approve")

    def decline(self, collect_id: str, reason: Optional[str] = None) -> Dict:
        """Decline a collect request with an optional reason."""
        params = {}
        if reason: params["reason"] = reason
        return self._req("POST", f"/v1/collects/{collect_id}/decline", params=params)


class PoolsResource(_Resource):
    """
    Group collection pools — collect from N people toward a shared goal.
    Auto-settles when goal met. Auto-refunds if deadline passes.
    """
    def create(
        self,
        goal_amount: int,
        organizer_account_id: str,
        payee_account_id: str,
        description: str,
        deadline: str,
        currency: str = "usd",
        on_deadline_miss: str = "refund_all",
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Create a group collection pool.
        goal_amount in cents. deadline in ISO 8601.
        on_deadline_miss: 'refund_all' (default) or 'settle_partial'
        """
        return self._req("POST", "/v1/pools/", json={
            "goal_amount": goal_amount,
            "currency": currency,
            "description": description,
            "organizer_account_id": organizer_account_id,
            "payee_account_id": payee_account_id,
            "deadline": deadline,
            "on_deadline_miss": on_deadline_miss,
        }, idempotency_key=idempotency_key)

    def get(self, pool_id: str) -> Dict:
        """Get a pool's current status and collected amount."""
        return self._req("GET", f"/v1/pools/{pool_id}")

    def contribute(
        self,
        pool_id: str,
        payer_account_id: str,
        amount: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Add a contribution to a pool.
        If this contribution causes collected_amount >= goal_amount,
        FlowPay auto-settles to the payee account.
        """
        return self._req("POST", f"/v1/pools/{pool_id}/contribute", json={
            "payer_account_id": payer_account_id,
            "amount": amount,
        }, idempotency_key=idempotency_key)

    def cancel(self, pool_id: str) -> Dict:
        """
        Cancel a pool. FlowPay issues reverse Nessie transfers
        for every contribution (refunds all contributors).
        Returns the list of refund_ids.
        """
        return self._req("POST", f"/v1/pools/{pool_id}/cancel")

    def contributions(self, pool_id: str) -> Dict:
        """List all individual contributions to a pool."""
        return self._req("GET", f"/v1/pools/{pool_id}/contributions")


class CorridorsResource(_Resource):
    """
    FlowBridge: Cross-border FX payment corridors.
    Lock a live exchange rate and remit at that rate.
    """
    def create(
        self,
        source_currency: str,
        target_currency: str,
        source_account_id: str,
        target_account_id: str,
        amount_target: int,
        description: str,
        lock_duration_minutes: int = 30,
        max_rate_drift_pct: float = 2.0,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Create a corridor with a locked FX rate.
        amount_target is in target currency cents (e.g. 4900 = $49.00 USD).
        Returns the live rate, locked rate, and source amount equivalent.
        """
        return self._req("POST", "/v1/corridors/", json={
            "source_currency": source_currency,
            "target_currency": target_currency,
            "source_account_id": source_account_id,
            "target_account_id": target_account_id,
            "amount_target": amount_target,
            "description": description,
            "lock_duration_minutes": lock_duration_minutes,
            "max_rate_drift_pct": max_rate_drift_pct,
        }, idempotency_key=idempotency_key)

    def get(self, corridor_id: str) -> Dict:
        return self._req("GET", f"/v1/corridors/{corridor_id}")

    def rate_check(self, corridor_id: str) -> Dict:
        """Check if the rate has drifted since locking."""
        return self._req("GET", f"/v1/corridors/{corridor_id}/rate-check")

    def remit(self, corridor_id: str) -> Dict:
        """
        Execute the cross-border transfer at the locked FX rate.
        Fails with rate_lock_expired (410) if lock timed out.
        Fails with rate_drift_exceeded (422) if FX moved too much.
        """
        return self._req("POST", f"/v1/corridors/{corridor_id}/remit")

    def list(self) -> List[Dict]:
        return self._req("GET", "/v1/corridors/")


class FXPoolsResource(_Resource):
    """
    FlowBridge: Multi-currency group collection.
    Each person pays in their own local currency. FlowPay handles FX.
    Auto-refunds in original currencies if rates drift.
    """
    def create(
        self,
        goal_amount_usd: int,
        organizer_account_id: str,
        payee_account_id: str,
        description: str,
        deadline: str,
        max_rate_drift_pct: float = 3.0,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """Create an FX-aware multi-currency pool. Goal is in USD cents."""
        return self._req("POST", "/v1/fxpools/", json={
            "goal_amount_usd": goal_amount_usd,
            "organizer_account_id": organizer_account_id,
            "payee_account_id": payee_account_id,
            "description": description,
            "deadline": deadline,
            "max_rate_drift_pct": max_rate_drift_pct,
        }, idempotency_key=idempotency_key)

    def get(self, pool_id: str) -> Dict:
        return self._req("GET", f"/v1/fxpools/{pool_id}")

    def contribute(
        self,
        pool_id: str,
        payer_account_id: str,
        currency: str,
        amount_local: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Contribute in any local currency.
        FlowPay locks the live FX rate, converts to USD, and deducts from goal.
        currency: 'inr', 'eur', 'gbp', 'usd', etc.
        amount_local: in that currency's cents.
        """
        return self._req("POST", f"/v1/fxpools/{pool_id}/contribute", json={
            "payer_account_id": payer_account_id,
            "currency": currency,
            "amount_local": amount_local,
        }, idempotency_key=idempotency_key)

    def contributions(self, pool_id: str) -> Dict:
        return self._req("GET", f"/v1/fxpools/{pool_id}/contributions")

    def cancel(self, pool_id: str) -> Dict:
        return self._req("POST", f"/v1/fxpools/{pool_id}/cancel")


class RecurringResource(_Resource):
    """Pre-authorized subscription pull payments."""
    def create(
        self,
        payee_account_id: str,
        payer_account_id: str,
        amount: int,
        description: str,
        interval: str = "monthly",
        max_occurrences: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict:
        """
        Create a recurring pull payment. Payer pre-authorizes.
        interval: 'daily', 'weekly', 'monthly', 'yearly'
        """
        return self._req("POST", "/v1/recurring/", json={
            "payee_account_id": payee_account_id,
            "payer_account_id": payer_account_id,
            "amount": amount,
            "description": description,
            "interval": interval,
            "max_occurrences": max_occurrences,
        }, idempotency_key=idempotency_key)

    def trigger(self, recurring_id: str) -> Dict:
        """Manually trigger one occurrence (in production: called by scheduler)."""
        return self._req("POST", f"/v1/recurring/{recurring_id}/trigger")

    def pause(self, recurring_id: str) -> Dict:
        return self._req("POST", f"/v1/recurring/{recurring_id}/pause")

    def cancel(self, recurring_id: str) -> Dict:
        return self._req("POST", f"/v1/recurring/{recurring_id}/cancel")


class AnalyticsResource(_Resource):
    def snapshot(self) -> Dict:
        """Real-time platform snapshot: volumes, statuses, recurring counts."""
        return self._req("GET", "/v1/analytics/")


class WebhooksResource(_Resource):
    def register(self, url: str, events: Optional[List[str]] = None) -> Dict:
        """Register a URL to receive webhook events."""
        return self._req("POST", "/v1/webhooks/", json={"url": url, "events": events})


class FlowPayClient:
    """
    FlowPay Python SDK.

    Example:
        client = FlowPayClient("http://localhost:8000")
        collect = client.collects.create(
            payee_account_id="...",
            payer_account_id="...",
            amount=4900,
            description="Invoice #123",
            expires_at="2026-03-10T00:00:00Z"
        )
        approved = client.collects.approve(collect["id"])
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout)

        # Resources
        self.collects = CollectsResource(self)
        self.pools = PoolsResource(self)
        self.corridors = CorridorsResource(self)
        self.fxpools = FXPoolsResource(self)
        self.recurring = RecurringResource(self)
        self.analytics = AnalyticsResource(self)
        self.webhooks = WebhooksResource(self)

    def _request(
        self,
        method: str,
        path: str,
        idempotency_key: Optional[str] = None,
        **kwargs,
    ) -> Any:
        url = self.base_url + path
        headers = kwargs.pop("headers", {})
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        resp = self._http.request(method, url, headers=headers, **kwargs)

        if resp.status_code >= 400:
            try:
                body = resp.json()
                error_detail = body.get("detail", body)
                if isinstance(error_detail, dict) and "error" in error_detail:
                    raise FlowPayError(resp.status_code, error_detail["error"])
                raise FlowPayError(resp.status_code, {"message": str(error_detail), "code": "api_error"})
            except FlowPayError:
                raise
            except Exception:
                raise FlowPayError(resp.status_code, {"message": resp.text, "code": "unknown_error"})

        return resp.json()

    def health(self) -> Dict:
        """Check API health."""
        return self._request("GET", "/v1/health")

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
