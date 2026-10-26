from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    full_name: str = Field(default="", min_length=0)
    phone_number: str = Field(min_length=5)
    email: str | None = None
    language: str = Field(default="en")


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    email: str | None = None
    language: str | None = None


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    full_name: str
    phone_number: str
    email: str | None
    language: str
    created_at: datetime