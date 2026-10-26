import hashlib
import hmac

import httpx

from app.core.config import settings

_MESSAGES_PATH = "/{api_version}/{phone_number_id}/messages"


def verify_webhook_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    """Verify Meta's `X-Hub-Signature-256` webhook header.

    Meta signs the RAW request body with HMAC-SHA256 using the app secret and
    sends it as `sha256=<hex>`. The comparison is constant-time to avoid timing
    attacks. Accepts both the full `sha256=<hex>` form and a bare hex digest.
    """
    if not payload or not app_secret:
        return False
    computed = hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature_header.strip()
    if "=" in provided:
        provided = provided.split("=", 1)[1].strip()
    return bool(provided) and hmac.compare_digest(provided, computed)


async def fetch_phone_number_info() -> dict:
    """Validate the configured access token against the Graph API.

    GETs `/{api_version}/{phone_number_id}` — the same lightweight call Meta's
    own "Test" button performs. Raises `httpx.HTTPStatusError` when the token
    is invalid/expired or the phone-number-id is wrong, so callers can surface
    the exact Graph API error.
    """
    url = (
        f"{settings.whatsapp_base_url}/{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}"
        "?fields=id,display_phone_number,quality_rating,verified_name"
    )
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def send_text_message(to_phone: str, text: str) -> dict:
    url = f"{settings.whatsapp_base_url}{_MESSAGES_PATH}".format(
        api_version=settings.whatsapp_api_version,
        phone_number_id=settings.whatsapp_phone_number_id,
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def extract_text_messages(payload: dict) -> list[dict]:
    """Return [{'from': phone, 'text': body, 'id': message_id}] text messages from a Meta webhook payload."""
    messages: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue
                messages.append(
                    {
                        "from": message.get("from", ""),
                        "text": message.get("text", {}).get("body", ""),
                        "id": message.get("id"),
                    }
                )
    return messages