"""
Outage alert dispatcher — turns a `health_checks` failure into an
URGENT, multi-channel notification that's deliberately designed to
NOT look like normal email so the admin can't ignore it.

Channels:
  • Email (Resend) — red HTML, 🚨🚨🚨 subject, distinct sender name
  • Telegram bot — uses chat_id + bot_token from `health_settings`
  • In-app banner — read separately from `/api/admin/health/active`

The email subject line is the most important visual differentiator
because that's what shows up in a notification preview. Format:
  "🚨🚨🚨 PRODUCTION OUTAGE — Tile Station — {label} DOWN"

A "recovered" follow-up is also sent so the admin knows when to
stop worrying.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import get_db

logger = logging.getLogger(__name__)


# ---------- Settings ----------

DEFAULT_SETTINGS = {
    "email_recipients": [],          # list[str]
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "alert_sender_name": "TILE STATION OUTAGE ALERT",
    "alert_sender_email": "",        # falls back to the account default if empty
    "test_mode": False,              # if True, skips actual delivery (admin "send test" uses this)
}


async def get_settings() -> dict:
    db = get_db()
    doc = await db.health_settings.find_one({"key": "alerting"}, {"_id": 0})
    cfg = {**DEFAULT_SETTINGS, **(doc or {})}
    return cfg


async def update_settings(payload: dict, updated_by: Optional[str] = None) -> dict:
    db = get_db()
    payload = dict(payload)
    payload["key"] = "alerting"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    if updated_by:
        payload["updated_by"] = updated_by
    await db.health_settings.update_one(
        {"key": "alerting"}, {"$set": payload}, upsert=True
    )
    return await get_settings()


# ---------- Email ----------

def _outage_email_html(check: dict, incident_id: str, state: dict, mode: str = "outage") -> str:
    """A deliberately ugly, attention-grabbing red email. The visual
    weight is intentional — this is the *one* email type that should
    look completely different from every other Tile Station email so
    the admin's brain notices it on a busy notification screen."""
    site_url = os.environ.get("SHOP_WEBSITE_URL", "https://tilestation.co.uk")
    admin_url = os.environ.get("ADMIN_URL", f"{site_url}/admin/health")
    label = check.get("label", "Endpoint")
    reason = check.get("failure_reason", "Unknown")
    failures = state.get("consecutive_failures", 0)
    elapsed_min = max(1, failures)  # 1 check ≈ 1 min

    if mode == "recovered":
        bg = "#16a34a"
        title = "✅ RECOVERED"
        sub = f"{label} is back online"
        body = (
            f"<p style='margin:0 0 14px 0;font-size:15px;'>"
            f"<b>{label}</b> has been responding healthily again. The incident is over.</p>"
            f"<p style='margin:0;font-size:13px;color:#444;'>You can stand down.</p>"
        )
    else:
        bg = "#dc2626"
        title = "🚨🚨🚨 PRODUCTION OUTAGE"
        sub = f"{label} is DOWN"
        body = (
            f"<p style='margin:0 0 6px 0;font-size:15px;'><b>What broke:</b> {label}</p>"
            f"<p style='margin:0 0 6px 0;font-size:15px;'><b>How long:</b> ~{elapsed_min} minute(s)</p>"
            f"<p style='margin:0 0 14px 0;font-size:15px;'><b>Why:</b> {reason}</p>"
            f"<p style='margin:0 0 6px 0;font-size:14px;color:#444;'>"
            f"Customers visiting tilestation.co.uk may be unable to see this section right now. "
            f"This is the SECOND consecutive failure — the bulletproof shield is serving last-known-good "
            f"data where possible, but you should still investigate.</p>"
        )

    return f"""\
<!doctype html><html><body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,Segoe UI,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;">
    <tr><td style="background:{bg};color:#fff;padding:22px 24px;border-radius:12px 12px 0 0;">
      <div style="font-size:13px;letter-spacing:0.18em;font-weight:700;opacity:0.9;">TILE STATION · MONITORING</div>
      <div style="font-size:26px;font-weight:900;margin-top:6px;line-height:1.1;">{title}</div>
      <div style="font-size:18px;font-weight:600;margin-top:6px;">{sub}</div>
    </td></tr>
    <tr><td style="background:#fff;padding:22px 24px;">
      {body}
      <p style="margin:18px 0 0 0;">
        <a href="{admin_url}" style="display:inline-block;background:#0f172a;color:#facc15;padding:14px 22px;border-radius:8px;font-weight:800;text-decoration:none;font-size:15px;">
          Open admin → Acknowledge
        </a>
      </p>
      <p style="margin:14px 0 0 0;font-size:11px;color:#888;">
        Incident ID: {incident_id} · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
        You'll get one of these every 5 minutes until you click Acknowledge or the issue resolves.
      </p>
    </td></tr>
  </table>
</body></html>"""


async def _send_email(check: dict, incident_id: str, state: dict, mode: str = "outage") -> bool:
    cfg = await get_settings()
    recipients = cfg.get("email_recipients") or []
    if not recipients:
        logger.warning("No email recipients configured for outage alerts")
        return False
    if cfg.get("test_mode"):
        logger.info(f"Test mode — skipping real email send to {recipients}")
        return True

    label = check.get("label", "Endpoint")
    if mode == "recovered":
        subject = f"✅ Recovered — {label} back online (Tile Station)"
    else:
        subject = f"🚨🚨🚨 PRODUCTION OUTAGE — {label} DOWN — Tile Station"
    html = _outage_email_html(check, incident_id, state, mode=mode)

    from services.email import send_email_notification
    sender_name = cfg.get("alert_sender_name") or "TILE STATION OUTAGE ALERT"
    try:
        ok = await send_email_notification(
            to_emails=recipients,
            subject=subject,
            html_content=html,
            from_name=sender_name,
        )
        return bool(ok)
    except Exception:
        logger.exception("Outage alert email failed to send")
        return False


# ---------- Telegram ----------

async def _send_telegram(check: dict, incident_id: str, state: dict, mode: str = "outage") -> bool:
    cfg = await get_settings()
    token = (cfg.get("telegram_bot_token") or "").strip()
    chat_id = (cfg.get("telegram_chat_id") or "").strip()
    if not token or not chat_id:
        return False
    if cfg.get("test_mode"):
        logger.info("Test mode — skipping real Telegram send")
        return True

    label = check.get("label", "Endpoint")
    if mode == "recovered":
        text = (
            f"✅ *RECOVERED — {label}*\n\n"
            f"Back online. The incident is over. You can stand down.\n\n"
            f"_Incident `{incident_id}`_"
        )
    else:
        reason = check.get("failure_reason", "Unknown")
        text = (
            f"🚨🚨🚨 *PRODUCTION OUTAGE*\n"
            f"*{label} is DOWN*\n\n"
            f"*Reason:* `{reason}`\n"
            f"*Failures:* {state.get('consecutive_failures', 0)} in a row\n\n"
            f"Open admin → Health to acknowledge.\n"
            f"_You'll get one of these every 5 min until you ack or the issue resolves._\n\n"
            f"_Incident `{incident_id}`_"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            if r.status_code == 200 and r.json().get("ok"):
                return True
            logger.warning(f"Telegram send returned non-200: {r.status_code} {r.text[:200]}")
            return False
    except Exception:
        logger.exception("Telegram send crashed")
        return False


# ---------- Public API ----------

async def dispatch_outage_alert(check: dict, incident_id: str, state: dict) -> dict:
    """Fan out to every configured channel. Returns a delivery report."""
    email_ok = await _send_email(check, incident_id, state, mode="outage")
    tg_ok = await _send_telegram(check, incident_id, state, mode="outage")
    logger.warning(
        f"OUTAGE ALERT for {check.get('label')} — incident={incident_id} "
        f"email={email_ok} telegram={tg_ok}"
    )
    return {"email": email_ok, "telegram": tg_ok, "incident_id": incident_id}


async def dispatch_recovery_alert(check: dict, incident_id: str) -> dict:
    """Followup when the endpoint comes back."""
    state = {"consecutive_failures": 0}
    email_ok = await _send_email(check, incident_id, state, mode="recovered")
    tg_ok = await _send_telegram(check, incident_id, state, mode="recovered")
    return {"email": email_ok, "telegram": tg_ok, "incident_id": incident_id}


async def dispatch_test_alert(recipient_email: Optional[str] = None) -> dict:
    """Triggered from the admin UI's "send test" button. Doesn't honor
    test_mode — this IS the test."""
    cfg = await get_settings()
    fake_check = {
        "label": "TEST ALERT — please ignore",
        "path": "/api/test",
        "failure_reason": "manual test from admin dashboard",
    }
    fake_state = {"consecutive_failures": 2}
    fake_incident = "test_" + datetime.now(timezone.utc).strftime("%H%M%S")

    # Optional override of recipient just for this test
    original_recipients = cfg.get("email_recipients") or []
    if recipient_email:
        await update_settings({**cfg, "email_recipients": [recipient_email]})
    try:
        email_ok = await _send_email(fake_check, fake_incident, fake_state, mode="outage")
        tg_ok = await _send_telegram(fake_check, fake_incident, fake_state, mode="outage")
    finally:
        if recipient_email:
            await update_settings({**cfg, "email_recipients": original_recipients})
    return {"email": email_ok, "telegram": tg_ok}
