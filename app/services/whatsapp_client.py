import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


async def send_text_message(to_phone: str, text: str) -> bool:
    """Send a WhatsApp text message via Meta Cloud API."""
    url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text[:4096]},
    }
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("WhatsApp send failed: %s %s", resp.status_code, resp.text[:200])
            return resp.status_code == 200
    except Exception as e:
        logger.error("WhatsApp send error: %s", e)
        return False


def extract_message_from_payload(payload: dict) -> tuple[str, str] | None:
    """
    Extract (phone_number, message_text) from Meta webhook payload.
    Returns None if not a text message.
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages", [])
        if not messages:
            return None
        msg = messages[0]
        if msg.get("type") != "text":
            return None
        phone = msg["from"]
        text = msg["text"]["body"]
        return phone, text
    except (KeyError, IndexError, TypeError):
        return None
