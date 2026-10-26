from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DoctorCreate(BaseModel):
    name: str = Field(min_length=1)
    title: str | None = None
    specialty: str | None = None
    bio: str | None = None
    service_ids: list[int] = Field(default_factory=list)


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    name: str
    title: str | None
    specialty: str | None
    bio: str | None
    is_active: bool
    created_at: datetime