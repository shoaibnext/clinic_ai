from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.conversation import ConversationDetail, ConversationRead, ConversationUpdate, MessageRead
from app.services import conversation_service, patient_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def get_conversations(
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return conversation_service.list_conversations(db, clinic)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_single_conversation(
    conversation_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    conversation = conversation_service.get_conversation(db, clinic, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    messages = conversation_service.messages_for(db, conversation)
    patient = patient_service.get_patient(db, clinic, conversation.patient_id)
    return ConversationDetail(
        id=conversation.id,
        clinic_id=conversation.clinic_id,
        patient_id=conversation.patient_id,
        status=conversation.status,
        channel=conversation.channel,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        patient=patient,
        messages=[MessageRead.model_validate(m) for m in messages],
    )


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def patch_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    """Staff takes over (human_active) or resolves a conversation (build plan 5.9)."""
    try:
        conversation = conversation_service.set_status(
            db, clinic, conversation_id, payload.status
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation