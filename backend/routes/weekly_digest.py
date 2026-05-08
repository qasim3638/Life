"""
Weekly Digest — Monday-morning email summarising recovery + referral + capture stats
across the previous 7 days. Uses verified Resend sender.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config import get_db
from services import get_current_user
from services.email import send_email_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weekly-digest", tags=["Weekly Digest"])


DEFAULTS = {
    "enabled": False,
    "recipient_emails": [],  # list of admin emails
    "weekday": 0,            # 0=Mon .. 6=Sun
    "hour_utc": 9,           # 9am UTC
}


class DigestSettings(BaseModel):
    enabled: bool | None = None
    recipient_emails: List[str] | None = None
    weekday: int | None = None
    hour_utc: int | None = None


def _require_super_admin(current_user: dict):
    if (current_user or {}).get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")


async def _load_settings(db) -> dict:
    doc = await db.website_settings.find_one({"key": "weekly_digest_settings"}, {"_id": 0})
    out = dict(DEFAULTS)
    if doc and isinstance(doc.get("value"), dict):
        out.update(doc["value"])
    out["recipient_emails"] = [e for e in (out.get("recipient_emails") or []) if isinstance(e, str) and "@" in e]
    return out


async def compute_digest_data(db, days: int = 7) -> Dict[str, Any]:
    """Aggregate the previous N days into a single dict."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # Abandoned-cart recoveries
    recovered_agg = await db.abandoned_carts.aggregate([
        {"$match": {"status": "recovered", "recovered_at": {"$gte": since}}},
        {"$group": {"_id": None, "value": {"$sum": "$cart_total"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    recovered = recovered_agg[0] if recovered_agg else {}

    abandoned_count = await db.abandoned_carts.count_documents({
        "status": "abandoned", "updated_at": {"$gte": since}
    })

    # Captured emails (welcome popup)
    captured_count = await db.popup_emails.count_documents({"captured_at": {"$gte": since}})

    # Codes redeemed (paid orders) by source — single aggregation
    codes_agg = await db.shop_orders.aggregate([
        {"$match": {"payment_status": "paid", "created_at": {"$gte": since}, "promo_code": {"$nin": [None, ""]}}},
        {"$lookup": {
            "from": "shop_discount_codes",
            "localField": "promo_code",
            "foreignField": "code",
            "as": "code_doc",
        }},
        {"$unwind": "$code_doc"},
        {"$group": {
            "_id": "$code_doc.source",
            "value": {"$sum": "$total"},
            "count": {"$sum": 1},
        }},
    ]).to_list(20)
    by_source = {row["_id"]: {"value": float(row.get("value") or 0), "count": int(row.get("count") or 0)} for row in codes_agg}

    # Top referrer (by paid revenue from FRIEND-XXXXXX codes used)
    top_ref_agg = await db.shop_orders.aggregate([
        {"$match": {"payment_status": "paid", "created_at": {"$gte": since}, "promo_code": {"$nin": [None, ""]}}},
        {"$lookup": {
            "from": "shop_discount_codes",
            "localField": "promo_code",
            "foreignField": "code",
            "as": "code_doc",
        }},
        {"$unwind": "$code_doc"},
        {"$match": {"code_doc.source": "referral"}},
        {"$group": {
            "_id": "$code_doc.referrer_email",
            "value": {"$sum": "$total"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"value": -1}},
        {"$limit": 1},
    ]).to_list(1)
    top_referrer = None
    if top_ref_agg and top_ref_agg[0].get("_id"):
        top_referrer = {
            "email": top_ref_agg[0]["_id"],
            "value": round(float(top_ref_agg[0].get("value") or 0), 2),
            "count": int(top_ref_agg[0].get("count") or 0),
        }

    return {
        "period_start": since.isoformat(),
        "period_end": now.isoformat(),
        "recovered_value": round(float(recovered.get("value") or 0), 2),
        "recovered_count": int(recovered.get("count") or 0),
        "abandoned_count": abandoned_count,
        "captured_emails": captured_count,
        "by_source": by_source,
        "top_referrer": top_referrer,
        "total_redemption_value": round(sum(s["value"] for s in by_source.values()), 2),
        "total_redemption_count": sum(s["count"] for s in by_source.values()),
    }


def _render_html(data: dict) -> str:
    period_start_str = datetime.fromisoformat(data["period_start"]).strftime("%d %b")
    period_end_str = datetime.fromisoformat(data["period_end"]).strftime("%d %b %Y")

    by_source = data.get("by_source", {})

    def src_row(key: str, label: str) -> str:
        s = by_source.get(key, {"value": 0, "count": 0})
        return f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;">{label}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">{s['count']}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:bold;">£{s['value']:.2f}</td>
        </tr>"""

    top = data.get("top_referrer")
    top_html = ""
    if top:
        top_html = f"""
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px;margin:18px 0;">
          <p style="margin:0;font-size:13px;color:#166534;text-transform:uppercase;letter-spacing:1px;">Top referrer</p>
          <p style="margin:4px 0 0 0;font-weight:bold;color:#14532D;font-size:16px;">{top['email']}</p>
          <p style="margin:2px 0 0 0;color:#166534;font-size:13px;">£{top['value']:.2f} from {top['count']} order(s)</p>
        </div>"""

    return f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;background:#fff;">
  <div style="background:#111;color:#F7EA1C;padding:24px;text-align:center;">
    <h1 style="margin:0;font-size:22px;letter-spacing:1px;">TILE STATION</h1>
    <p style="margin:6px 0 0 0;font-size:13px;opacity:0.85;">Weekly digest — {period_start_str} to {period_end_str}</p>
  </div>
  <div style="padding:28px;">
    <table cellpadding="0" cellspacing="0" style="width:100%;margin:0 0 18px 0;">
      <tr>
        <td style="width:50%;padding:14px;background:#FFFBE6;border-radius:8px;text-align:center;">
          <div style="font-size:11px;color:#666;letter-spacing:1px;text-transform:uppercase;">Recovered</div>
          <div style="font-size:26px;font-weight:bold;color:#111;margin-top:4px;">£{data['recovered_value']:.2f}</div>
          <div style="font-size:12px;color:#777;margin-top:2px;">{data['recovered_count']} basket(s)</div>
        </td>
        <td style="width:6px;"></td>
        <td style="width:50%;padding:14px;background:#F0FDF4;border-radius:8px;text-align:center;">
          <div style="font-size:11px;color:#166534;letter-spacing:1px;text-transform:uppercase;">New emails captured</div>
          <div style="font-size:26px;font-weight:bold;color:#14532D;margin-top:4px;">{data['captured_emails']}</div>
          <div style="font-size:12px;color:#166534;margin-top:2px;">via welcome popup</div>
        </td>
      </tr>
    </table>

    <table style="width:100%;border-collapse:collapse;margin-top:8px;">
      <thead>
        <tr style="background:#F6F6F6;">
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#666;">Codes redeemed</th>
          <th style="padding:10px 12px;text-align:right;font-size:12px;color:#666;">Orders</th>
          <th style="padding:10px 12px;text-align:right;font-size:12px;color:#666;">Revenue</th>
        </tr>
      </thead>
      <tbody>
        {src_row('abandoned_cart', 'Abandoned-cart (BACK)')}
        {src_row('referral', 'Referral (FRIEND)')}
        {src_row('welcome_popup', 'Welcome popup (WELCOME)')}
        {src_row('manual', 'Manual / one-off')}
        <tr>
          <td style="padding:12px;font-weight:bold;">Total</td>
          <td style="padding:12px;text-align:right;font-weight:bold;">{data['total_redemption_count']}</td>
          <td style="padding:12px;text-align:right;font-weight:bold;">£{data['total_redemption_value']:.2f}</td>
        </tr>
      </tbody>
    </table>

    {top_html}

    <p style="color:#777;font-size:12px;margin-top:22px;text-align:center;">
      Open the <a href="https://tilestation.co.uk/admin/promo-codes" style="color:#16A34A;">Promo Codes admin</a>
      &middot; <a href="https://tilestation.co.uk/admin/abandoned-baskets" style="color:#16A34A;">Abandoned Baskets</a>
      for the full picture.
    </p>
  </div>
</div>"""


async def send_digest_now() -> dict:
    """Trigger a digest send immediately (used by the scheduler tick + the manual admin button)."""
    db = get_db()
    settings = await _load_settings(db)
    if not settings.get("enabled"):
        return {"status": "disabled"}
    recipients = settings.get("recipient_emails") or []
    if not recipients:
        return {"status": "no_recipients"}

    data = await compute_digest_data(db, days=7)
    html = _render_html(data)

    sent = await send_email_notification(
        to_emails=recipients,
        subject=f"Tile Station — weekly recovery digest (£{data['recovered_value']:.2f} + {data['captured_emails']} new emails)",
        html_content=html,
        from_name="Tile Station",
    )

    await db.weekly_digest_log.insert_one({
        "sent_at": datetime.now(timezone.utc),
        "recipients": recipients,
        "ok": bool(sent),
        "data": data,
    })
    return {"status": "ok" if sent else "send_failed", "recipients": recipients, "data": data}


# ============ ROUTES ============

@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    if (current_user or {}).get("role") not in {"super_admin", "admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    return await _load_settings(db)


@router.put("/settings")
async def update_settings(payload: DigestSettings, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()
    current = await _load_settings(db)
    if payload.enabled is not None:
        current["enabled"] = bool(payload.enabled)
    if payload.recipient_emails is not None:
        current["recipient_emails"] = [e.strip().lower() for e in payload.recipient_emails if isinstance(e, str) and "@" in e]
    if payload.weekday is not None:
        current["weekday"] = max(0, min(6, int(payload.weekday)))
    if payload.hour_utc is not None:
        current["hour_utc"] = max(0, min(23, int(payload.hour_utc)))
    await db.website_settings.update_one(
        {"key": "weekly_digest_settings"},
        {"$set": {"value": current, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return current


@router.get("/preview")
async def preview_digest(current_user: dict = Depends(get_current_user)):
    """Return the computed numbers + rendered HTML so super admin can preview before enabling."""
    if (current_user or {}).get("role") not in {"super_admin", "admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    data = await compute_digest_data(db, days=7)
    return {"data": data, "html": _render_html(data)}


@router.post("/send-now")
async def send_now(current_user: dict = Depends(get_current_user)):
    """Manual trigger for super admin (useful while testing)."""
    _require_super_admin(current_user)
    return await send_digest_now()
