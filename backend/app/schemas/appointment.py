from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    patient_id: int = Field(gt=0)
    service_id: int | None = None
    doctor_id: int | None = None
    service_label: str | None = None
    scheduled_at: datetime | None = None
    source: str = Field(default="whatsapp")
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    doctor_id: int | None = None
    service_id: int | None = None
    service_label: str | None = None
    notes: str | None = None


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    patient_id: int
    doctor_id: int | None
    service_id: int | None
    service_label: str | None
    scheduled_at: datetime | None
    status: str
    notes: str | None
    source: str
    created_at: datetime