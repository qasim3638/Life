"""
Admin routes for the Sample → Order Conversion Followup automation.

  GET  /api/admin/sample-followups/eligible   — preview list of orders
                                                that WOULD receive a
                                                followup email today
  POST /api/admin/sample-followups/run-now    — manually trigger the
                                                daily pass (idempotent)
  GET  /api/admin/sample-followups/sent       — recent followups sent
                                                (last 30 days)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from services import get_current_user
from config import get_db

router = APIRouter(prefix="/admin/sample-followups", tags=["Sample Followups"])


def _require_admin(user: Optional[dict]) -> None:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = (user or {}).get("role") or ""
    if role not in ("admin", "super_admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/eligible")
async def list_eligible(
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """Dry-run preview: which orders WOULD receive a followup right now,
    plus the reason any are skipped."""
    _require_admin(current_user)
    from services.sample_followup import list_eligible_preview
    rows = await list_eligible_preview(limit=limit)
    return {
        "rows": rows,
        "would_send_count": sum(1 for r in rows if r.get("will_send")),
        "total_in_window": len(rows),
    }


@router.post("/run-now")
async def trigger_pass(current_user: dict = Depends(get_current_user)):
    """[Deprecated] Bulk-send all eligible. Kept for back-compat with the
    test endpoint, but the canonical flow is per-order manual review
    via /pending and /{order_id}/send."""
    _require_admin(current_user)
    from services.sample_followup import run_followup_pass
    summary = await run_followup_pass()
    return {"ok": True, "summary": summary}


@router.get("/pending")
async def pending_followups(
    current_user: dict = Depends(get_current_user),
):
    """Sample orders delivered 4-14 days ago that the owner can review
    and choose to email. Each row carries enough info for the admin UI
    to render a preview without further round-trips."""
    _require_admin(current_user)
    from services.sample_followup import (
        list_eligible_preview,
        FULL_SIZE_SAMPLE_REFUND_GBP,
    )
    rows = await list_eligible_preview(limit=500)
    # Only show rows that are genuinely actionable
    actionable = [r for r in rows if r.get("will_send")]
    skipped = [r for r in rows if not r.get("will_send")]
    return {
        "actionable": actionable,
        "skipped": skipped,
        "actionable_count": len(actionable),
        "voucher_per_full_size_gbp": FULL_SIZE_SAMPLE_REFUND_GBP,
    }


@router.get("/{sample_order_id}/preview")
async def preview_one(
    sample_order_id: str,
    include_voucher: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Render the email body the customer WOULD receive — for the admin
    to eyeball before clicking Send. Does not write anything."""
    _require_admin(current_user)
    db = get_db()
    order = await db.sample_orders.find_one({"id": sample_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sample order not found")

    from services.sample_followup import (
        _classify_order,
        FULL_SIZE_SAMPLE_REFUND_GBP,
    )
    free_count, paid_count, total_paid = _classify_order(order)
    voucher_amount = 0.0
    if include_voucher and paid_count > 0:
        voucher_amount = round(min(total_paid, paid_count * FULL_SIZE_SAMPLE_REFUND_GBP), 2)

    # Minimal preview: subject line + plain summary. The actual rendered
    # HTML is only generated at send time (from services.email).
    safe_name = (order.get("customer_name") or "there").split(" ")[0]
    if voucher_amount > 0:
        subject = f"Hi {safe_name}, here's £{voucher_amount:.0f} off your tile order"
    else:
        subject = f"Hi {safe_name}, ready to order your tiles?"
    summary_bits = []
    if free_count:
        summary_bits.append(f"{free_count} free sample{'s' if free_count != 1 else ''}")
    if paid_count:
        summary_bits.append(f"{paid_count} Full Size sample{'s' if paid_count != 1 else ''}")

    return {
        "sample_order_id": sample_order_id,
        "order_number": order.get("order_number"),
        "customer_email": order.get("customer_email"),
        "customer_name": order.get("customer_name"),
        "subject": subject,
        "free_count": free_count,
        "paid_count": paid_count,
        "total_paid_gbp": total_paid,
        "voucher_offered": voucher_amount > 0,
        "voucher_amount_gbp": voucher_amount,
        "products": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "image": p.get("image"),
                "sample_type": p.get("sample_type", "free_cut"),
                "price_gbp": p.get("price_gbp", 0),
            }
            for p in (order.get("products") or [])
        ],
        "summary_text": " + ".join(summary_bits) or "your samples",
    }


@router.post("/{sample_order_id}/send")
async def send_one_followup(
    sample_order_id: str,
    include_voucher: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Owner-triggered: send the followup email for ONE order.

    Idempotent — second click is a no-op. The voucher is only minted
    if `include_voucher=true` AND the order has at least one paid
    Full Size sample. Owner can choose to send the email without a
    voucher (e.g. for free-only orders, or to skip the discount on a
    customer they don't want to upsell)."""
    _require_admin(current_user)
    db = get_db()

    from services import sample_followup as sf
    if await sf._already_followed_up(db, sample_order_id):
        return {"ok": True, "skipped": "already_sent"}

    order = await db.sample_orders.find_one({"id": sample_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sample order not found")

    customer_email = (order.get("customer_email") or "").lower().strip()
    if not customer_email:
        raise HTTPException(status_code=400, detail="Order has no customer email")

    free_count, paid_count, total_paid = sf._classify_order(order)
    voucher_code = None
    voucher_amount = 0.0
    if include_voucher and paid_count > 0:
        voucher_amount = round(min(total_paid, paid_count * sf.FULL_SIZE_SAMPLE_REFUND_GBP), 2)
        if voucher_amount > 0:
            voucher_code = sf._voucher_code()
            await sf._create_voucher(
                db,
                code=voucher_code,
                amount_gbp=voucher_amount,
                customer_email=customer_email,
            )

    try:
        from services.email import send_sample_followup_email
        result = await send_sample_followup_email(
            customer_email=customer_email,
            customer_name=order.get("customer_name") or "there",
            order=order,
            voucher_code=voucher_code,
            voucher_amount_gbp=voucher_amount,
            free_count=free_count,
            paid_count=paid_count,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Email send failed: {e}")

    if not result.get("sent"):
        raise HTTPException(status_code=502, detail=result.get("error") or "Email send failed")

    await sf._record_followup_sent(
        db,
        sample_order_id=sample_order_id,
        order_number=order.get("order_number") or "",
        customer_email=customer_email,
        voucher_code=voucher_code,
        voucher_amount_gbp=voucher_amount,
    )

    return {
        "ok": True,
        "sent": True,
        "voucher_code": voucher_code,
        "voucher_amount_gbp": voucher_amount,
        "subject_variant": "with_discount" if voucher_code else "soft_nudge",
    }


@router.post("/{sample_order_id}/skip")
async def skip_one_followup(
    sample_order_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Mark a followup as skipped so it stops appearing in the
    review queue. No email sent. Idempotent."""
    _require_admin(current_user)
    db = get_db()
    from services import sample_followup as sf
    if await sf._already_followed_up(db, sample_order_id):
        return {"ok": True, "already": True}

    order = await db.sample_orders.find_one({"id": sample_order_id}, {"_id": 0, "customer_email": 1, "order_number": 1})
    if not order:
        raise HTTPException(status_code=404, detail="Sample order not found")

    await sf._record_followup_sent(
        db,
        sample_order_id=sample_order_id,
        order_number=order.get("order_number") or "",
        customer_email=(order.get("customer_email") or "").lower().strip(),
        voucher_code=None,
        voucher_amount_gbp=0.0,
    )
    # Tag this row as a skip (vs send) so audit can tell them apart
    await db.sample_followup_sent.update_one(
        {"sample_order_id": sample_order_id},
        {"$set": {"manually_skipped": True}},
    )
    return {"ok": True, "skipped": True}


@router.get("/sent")
async def recent_sent(
    days: int = Query(30, ge=1, le=180),
    current_user: dict = Depends(get_current_user),
):
    """Recent followups sent — for accountability + spot-checking."""
    _require_admin(current_user)
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = db.sample_followup_sent.find(
        {"sent_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("sent_at", -1).limit(500)
    rows = [r async for r in cursor]
    # Coerce datetimes to ISO for JSON
    for r in rows:
        if isinstance(r.get("sent_at"), datetime):
            r["sent_at"] = r["sent_at"].isoformat()
    return {
        "rows": rows,
        "total": len(rows),
        "window_days": days,
    }
