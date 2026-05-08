"""
WhatsApp message scheduler.
Processes the whatsapp_queue collection and sends messages at their scheduled time.
Runs as a background task in the FastAPI application.
"""
import asyncio
import logging
from datetime import datetime, timezone
from services.whatsapp_service import send_whatsapp_template_message

logger = logging.getLogger(__name__)

_scheduler_task = None
_db_ref = None


def start_whatsapp_scheduler(db):
    """Start the background scheduler loop."""
    global _scheduler_task, _db_ref
    _db_ref = db
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("WhatsApp message scheduler started")


async def _scheduler_loop():
    """Check for pending messages every 60 seconds and send them."""
    while True:
        try:
            await _process_pending_messages()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


async def _process_pending_messages():
    """Find and send all messages whose scheduled time has passed."""
    if _db_ref is None:
        return

    now = datetime.now(timezone.utc)

    # Check if WhatsApp messaging is enabled
    settings = await _db_ref.whatsapp_settings.find_one({"_id": "config"})
    if not settings or not settings.get("enabled", False):
        return

    template_name = settings.get("template_name", "")
    if not template_name:
        return

    # Find messages ready to send
    cursor = _db_ref.whatsapp_queue.find({
        "status": "pending",
        "scheduled_at": {"$lte": now.isoformat()},
    })

    messages = await cursor.to_list(50)

    for msg in messages:
        try:
            # Build parameters - first name
            first_name = (msg.get("customer_name", "") or "").split()[0] if msg.get("customer_name") else "there"
            parameters = [first_name]

            result = await send_whatsapp_template_message(
                recipient_phone=msg["phone"],
                template_name=template_name,
                language_code=settings.get("language_code", "en"),
                parameters=parameters,
            )

            if result.get("success"):
                await _db_ref.whatsapp_queue.update_one(
                    {"id": msg["id"]},
                    {"$set": {
                        "status": "sent",
                        "sent_at": now.isoformat(),
                        "message_id": result.get("message_id"),
                    }},
                )
                logger.info(f"WhatsApp sent to {msg['phone']} ({first_name})")
            else:
                error = result.get("error", "Unknown error")
                retry_count = msg.get("retry_count", 0)
                if retry_count >= 3:
                    await _db_ref.whatsapp_queue.update_one(
                        {"id": msg["id"]},
                        {"$set": {"status": "failed", "error": error, "failed_at": now.isoformat()}},
                    )
                    logger.error(f"WhatsApp permanently failed for {msg['phone']}: {error}")
                else:
                    await _db_ref.whatsapp_queue.update_one(
                        {"id": msg["id"]},
                        {"$set": {"error": error, "retry_count": retry_count + 1}},
                    )
                    logger.warning(f"WhatsApp retry {retry_count + 1} for {msg['phone']}: {error}")

        except Exception as e:
            logger.error(f"Error processing message {msg.get('id')}: {e}")
