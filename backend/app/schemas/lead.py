from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    service: str | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    source: str = Field(default="whatsapp")
    notes: str | None = None


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    service: str | None = None
    status: str | None = None
    notes: str | None = None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    name: str | None
    phone: str | None
    email: str | None
    service: str | None
    preferred_date: str | None
    preferred_time: str | None
    status: str
    source: str
    notes: str | None
    created_at: datetime