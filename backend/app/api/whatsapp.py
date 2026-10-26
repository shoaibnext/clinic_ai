import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.ai.orchestrator import handle_message
from app.core.config import settings
from app.database.database import get_db
from app.schemas.whatsapp import WhatsAppStatusResponse, WhatsAppTestRequest, WhatsAppTestResponse
from app.services import clinic_service, conversation_service, patient_service, whatsapp_service
from app.services.whatsapp_service import send_text_message, verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


@router.get("/webhooks/whatsapp")
@router.get("/whatsapp/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_webhook_verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/webhooks/whatsapp")
@router.post("/whatsapp/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Meta WhatsApp Cloud API webhook. Resolves the clinic tenant by its
    configured WhatsApp phone-number-id, then runs the AI receptionist loop.

    When WHATSAPP_APP_SECRET is set (production), the X-Hub-Signature-256
    header is verified against the RAW request body before anything else;
    requests with a missing or invalid signature are rejected with 403.
    """
    raw_body = await request.body()

    if settings.whatsapp_app_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_webhook_signature(raw_body, signature, settings.whatsapp_app_secret):
            logger.warning("Rejected webhook: invalid or missing X-Hub-Signature-256")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    else:
        logger.warning(
            "WHATSAPP_APP_SECRET is not configured — webhook signature verification is disabled (dev mode)"
        )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    messages = whatsapp_service.extract_text_messages(payload)

    if not messages:
        return {"status": "ok"}

    phone_number_id = ""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            phone_number_id = (
                change.get("value", {}).get("metadata", {}).get("phone_number_id", "")
            )
            if phone_number_id:
                break

    clinic = clinic_service.get_clinic_by_whatsapp_phone(db, phone_number_id)
    if clinic is None:
        # Fallback: a single WhatsApp account maps to the first active clinic.
        clinic = clinic_service.list_clinics(db)
        clinic = clinic[0] if clinic else None
    if clinic is None:
        logger.warning("No clinic configured for WhatsApp phone number id %s", phone_number_id)
        return {"status": "ok"}

    for message in messages:
        phone = message["from"]
        text = message["text"]
        message_id = message.get("id")

        patient = patient_service.get_or_create_patient(db, clinic, phone)
        conversation = conversation_service.get_or_create_conversation(
            db, clinic, patient, whatsapp_message_id=message_id
        )
        conversation_service.add_message(
            db, clinic, conversation.id, direction="in", body=text
        )

        reply = await handle_message(
            db, clinic=clinic, patient=patient, conversation=conversation, user_message=text
        )

        conversation_service.add_message(
            db, clinic, conversation.id, direction="out", body=reply
        )
        db.commit()

        if settings.whatsapp_phone_number_id and settings.whatsapp_access_token:
            # Clinic-level number override
            if clinic.whatsapp_phone_number_id:
                settings_holder = settings
                original = settings.whatsapp_phone_number_id
                settings_holder.whatsapp_phone_number_id = clinic.whatsapp_phone_number_id
                try:
                    await send_text_message(phone, reply)
                except Exception as exc:  # noqa: BLE001
                    # The reply is already persisted on the Conversation. A delivery
                    # failure (expired/revoked token, Graph API 4xx/5xx) must NOT fail
                    # the webhook — Meta retries non-2xx responses and would re-process
                    # the same message (duplicate saves/replies).
                    logger.warning("WhatsApp outbound reply failed for %s: %s", phone, exc)
                finally:
                    settings_holder.whatsapp_phone_number_id = original
            else:
                try:
                    await send_text_message(phone, reply)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("WhatsApp outbound reply failed for %s: %s", phone, exc)

    return {"status": "ok"}


@router.get("/whatsapp/status", response_model=WhatsAppStatusResponse)
async def whatsapp_status():
    """Connection diagnostic for the WhatsApp Cloud API.

    Reports which credentials are configured (never echoes secrets) and, when
    credentials are present, validates them live against the Graph API — the
    same call Meta's "Test" button makes. Use this to confirm the app can talk
    to WhatsApp BEFORE wiring up the webhook.
    """
    response = WhatsAppStatusResponse(
        configured=bool(settings.whatsapp_phone_number_id and settings.whatsapp_access_token),
        waba_id=settings.whatsapp_waba_id,
        phone_number_id=settings.whatsapp_phone_number_id,
        access_token="set" if settings.whatsapp_access_token else "not set",
        webhook_verify_token="set" if settings.whatsapp_webhook_verify_token else "not set",
        app_secret="set" if settings.whatsapp_app_secret else "not set",
        api_version=settings.whatsapp_api_version,
    )

    if not response.configured:
        response.phone_number_id = "not set"
        return response

    try:
        info = await whatsapp_service.fetch_phone_number_info()
        response.graph_api = {"ok": True, "info": info}
    except httpx.HTTPStatusError as exc:
        error = {}
        try:
            error = exc.response.json().get("error", {})
        except Exception:
            error = {"message": exc.response.text[:500]}
        response.graph_api = {
            "ok": False,
            "status_code": exc.response.status_code,
            "code": error.get("code"),
            "error": error.get("message", str(exc)),
        }
    except Exception as exc:  # network/DNS problems, etc.
        response.graph_api = {"ok": False, "error": str(exc)}

    return response


@router.post("/whatsapp/test", response_model=WhatsAppTestResponse)
async def whatsapp_test(payload: WhatsAppTestRequest):
    """Send a live outbound test message to a phone number.

    The fastest end-to-end connectivity check: healthy creds + a valid number
    in Meta's allowlist (test/development mode) or a user who replied "join"
    (production) will receive `payload.text`.
    """
    if not (settings.whatsapp_phone_number_id and settings.whatsapp_access_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "WhatsApp is not configured yet. Set WHATSAPP_PHONE_NUMBER_ID and "
                "WHATSAPP_ACCESS_TOKEN in backend/.env, then restart the API."
            ),
        )
    try:
        await send_text_message(payload.to_phone, payload.text)
    except httpx.HTTPStatusError as exc:
        error = {}
        try:
            error = exc.response.json().get("error", {})
        except Exception:
            error = {"message": exc.response.text[:500]}
        return WhatsAppTestResponse(
            ok=False,
            status_code=exc.response.status_code,
            detail=error.get("message", str(exc)) or str(exc),
        )
    except Exception as exc:
        return WhatsAppTestResponse(ok=False, detail=str(exc))
    return WhatsAppTestResponse(ok=True, status_code=200, detail="Message sent")