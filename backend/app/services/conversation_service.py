from sqlalchemy.orm import Session

from app.database.models import Clinic, Conversation, Message, Patient

VALID_STATUSES = {"ai_active", "human_requested", "human_active", "resolved"}


def get_conversation(db: Session, clinic: Clinic, conversation_id: int) -> Conversation | None:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.clinic_id != clinic.id:
        return None
    return conversation


def get_or_create_conversation(
    db: Session,
    clinic: Clinic,
    patient: Patient,
    *,
    channel: str = "whatsapp",
    whatsapp_message_id: str | None = None,
) -> Conversation:
    if whatsapp_message_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.clinic_id == clinic.id,
                Conversation.whatsapp_message_id == whatsapp_message_id,
            )
            .first()
        )
        if conversation:
            return conversation

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.clinic_id == clinic.id,
            Conversation.patient_id == patient.id,
            Conversation.status != "resolved",
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if conversation is None:
        conversation = Conversation(
            clinic_id=clinic.id,
            patient_id=patient.id,
            whatsapp_message_id=whatsapp_message_id,
            channel=channel,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def add_message(db: Session, clinic: Clinic, conversation_id: int, *, direction: str, body: str) -> Message:
    message = Message(
        clinic_id=clinic.id,
        conversation_id=conversation_id,
        direction=direction,
        body=body,
    )
    db.add(message)
    db.flush()
    return message


def list_conversations(db: Session, clinic: Clinic, limit: int = 50) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.clinic_id == clinic.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def messages_for(db: Session, conversation: Conversation, limit: int = 20) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id.asc())
        .limit(limit)
        .all()
    )


def history(db: Session, conversation: Conversation, limit: int = 10) -> list[dict]:
    """Conversation transcript for the LLM, oldest first."""
    rows = messages_for(db, conversation, limit=limit)
    return [{"role": "assistant" if m.direction == "out" else "user", "content": m.body} for m in rows]


def conversation_state(conversation: Conversation) -> dict:
    return dict(conversation.state or {})


def save_state(db: Session, conversation: Conversation, state: dict) -> None:
    conversation.state = state
    db.flush()


def set_status(db: Session, clinic: Clinic, conversation_id: int, status: str) -> Conversation | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")
    conversation = get_conversation(db, clinic, conversation_id)
    if conversation is None:
        return None
    conversation.status = status
    db.commit()
    db.refresh(conversation)
    return conversation