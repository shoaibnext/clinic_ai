from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    duration_minutes: int = Field(default=30, ge=5, le=240)
    price: str | None = None
    doctor_ids: list[int] = Field(default_factory=list)


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    name: str
    description: str | None
    duration_minutes: int
    price: str | None
    is_active: bool
    created_at: datetime