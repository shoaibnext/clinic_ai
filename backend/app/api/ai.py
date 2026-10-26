import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.orchestrator import handle_message, process_message
from app.database.database import get_db
from app.schemas.ai import ChatRequest, ChatResponse, TestChatRequest, TestChatResponse
from app.services import clinic_service, conversation_service, patient_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


def _llm_error(detail: str) -> HTTPException:
    """Return a clean 502 (Bad Gateway) with the provider's message.

    Prevents raw 500s from LLM/provider failures (bad/expired keys, provider
    outages, rate limits) without leaking secrets.
    """
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"AI service unavailable: {detail}",
    )


@router.get("/ai/test")
async def ai_test():
    """Provider connectivity check."""
    from app.ai.client import get_model, get_llm

    try:
        get_llm()
        return {"status": "configured", "model": get_model()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/test-chat", response_model=TestChatResponse)
async def test_chat(payload: TestChatRequest):
    """Level-1 endpoint (build plan Step 5.1): plain LLM chat for a clinic name."""
    try:
        response = await process_message(payload.clinic_name, payload.message)
    except Exception as exc:
        logger.warning("test-chat failed: %s", exc)
        raise _llm_error(str(exc)) from exc
    return TestChatResponse(response=response)


@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    clinic = None
    if payload.clinic_id is not None:
        clinic = clinic_service.get_clinic(db, payload.clinic_id)
    elif payload.clinic_slug:
        clinic = clinic_service.get_clinic_by_slug(db, payload.clinic_slug)
    if clinic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")

    conversation = None
    patient = None
    if payload.conversation_id is not None:
        conversation = conversation_service.get_conversation(db, clinic, payload.conversation_id)
        if conversation is not None:
            patient = patient_service.get_patient(db, clinic, conversation.patient_id)

    if conversation is None:
        patient = patient or patient_service.get_or_create_patient(
            db, clinic, phone_number="test-ai-chat", language="en"
        )
        conversation = conversation_service.get_or_create_conversation(
            db, clinic, patient, channel="web"
        )

    conversation_service.add_message(db, clinic, conversation.id, direction="in", body=payload.message)
    try:
        reply = await handle_message(
            db, clinic=clinic, patient=patient, conversation=conversation, user_message=payload.message
        )
    except Exception as exc:
        logger.warning("ai/chat failed: %s", exc)
        raise _llm_error(str(exc)) from exc
    conversation_service.add_message(db, clinic, conversation.id, direction="out", body=reply)
    db.commit()

    state = conversation_service.conversation_state(conversation)
    return ChatResponse(
        reply=reply,
        intent=state.get("intent") or "UNKNOWN",
        confidence=float(state.get("confidence", 0.0)),
        conversation_id=conversation.id,
    )