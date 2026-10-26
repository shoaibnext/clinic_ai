from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClinicCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    timezone: str = "Asia/Karachi"
    admin_email: str | None = None
    admin_password: str | None = None
    whatsapp_phone_number_id: str | None = None
    emergency_instructions: str | None = None


class ClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    phone: str | None
    email: str | None
    address: str | None
    timezone: str
    status: str
    whatsapp_phone_number_id: str | None
    created_at: datetime


class ClinicOnboardResponse(ClinicRead):
    api_key: str