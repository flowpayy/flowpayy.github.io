from fastapi import APIRouter
from datetime import datetime, timezone
from app.api.collect import fake_collect_db
from app.api.pool import fake_pool_db, fake_contributions_db
from app.api.recurring import recurring_db

router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])

@router.get("")
@router.get("/")
async def get_analytics():
    """
    Real-time platform analytics — gives judges/developers a high-level 
    view of all activity going through the FlowPay platform.
    """
    collects = list(fake_collect_db.values())
    pools = list(fake_pool_db.values())
    recurring = list(recurring_db.values())

    total_collect_volume = sum(c.amount for c in collects if c.status == "approved")
    total_pool_volume = sum(p.collected_amount for p in pools if p.status == "funded")
    total_refunded = sum(
        sum(contrib["amount"] for contrib in fake_contributions_db.get(p.id, []))
        for p in pools if p.status == "cancelled"
    )

    return {
        "object": "analytics_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collects": {
            "total": len(collects),
            "pending": sum(1 for c in collects if c.status == "pending"),
            "approved": sum(1 for c in collects if c.status == "approved"),
            "declined": sum(1 for c in collects if c.status == "declined"),
            "expired": sum(1 for c in collects if c.status == "expired"),
            "volume_settled_cents": total_collect_volume
        },
        "pools": {
            "total": len(pools),
            "collecting": sum(1 for p in pools if p.status == "collecting"),
            "funded": sum(1 for p in pools if p.status == "funded"),
            "cancelled": sum(1 for p in pools if p.status == "cancelled"),
            "volume_settled_cents": total_pool_volume,
            "volume_refunded_cents": total_refunded
        },
        "recurring": {
            "total": len(recurring),
            "active": sum(1 for r in recurring if r.status == "active"),
            "paused": sum(1 for r in recurring if r.status == "paused"),
            "total_executions": sum(r.occurrences_count for r in recurring)
        },
        "combined": {
            "total_volume_settled_cents": total_collect_volume + total_pool_volume,
            "total_transactions": len(collects) + len(pools)
        }
    }
