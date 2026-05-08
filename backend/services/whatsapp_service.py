"""
WhatsApp Cloud API service for sending template messages.
Handles Meta Graph API communication and message delivery.
"""
import httpx
import logging
import os

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = "v21.0"
WHATSAPP_API_BASE = "https://graph.facebook.com"


async def send_whatsapp_template_message(
    recipient_phone: str,
    template_name: str,
    language_code: str = "en",
    parameters: list = None,
) -> dict:
    """
    Send a WhatsApp template message via Meta Cloud API.

    Args:
        recipient_phone: E.164 format phone number (e.g., +447700900000)
        template_name: Approved template name in WhatsApp Manager
        language_code: Template language code
        parameters: List of string values for {{1}}, {{2}} etc.

    Returns:
        dict with success status and message_id
    """
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.warning("WhatsApp credentials not configured - message not sent")
        return {"success": False, "error": "WhatsApp API credentials not configured"}

    url = f"{WHATSAPP_API_BASE}/{WHATSAPP_API_VERSION}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    if parameters:
        payload["template"]["components"] = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in parameters],
            }
        ]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            message_id = result.get("messages", [{}])[0].get("id", "unknown")
            logger.info(f"WhatsApp message sent to {recipient_phone} (ID: {message_id})")
            return {"success": True, "message_id": message_id}
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error(f"WhatsApp API error {e.response.status_code}: {error_body}")
        return {"success": False, "error": f"API error {e.response.status_code}: {error_body}"}
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return {"success": False, "error": str(e)}
