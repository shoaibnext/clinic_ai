from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.patient import PatientRead


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    direction: str
    body: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    patient_id: int
    status: str
    channel: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    patient: PatientRead | None = None
    messages: list[MessageRead] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    status: str = Field(description="ai_active | human_requested | human_active | resolved")