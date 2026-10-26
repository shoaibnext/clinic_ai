from datetime import date, time as dtime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.services import availability_service

router = APIRouter(prefix="/availability", tags=["availability"])


class AvailabilityCreate(BaseModel):
    doctor_id: int | None = None
    service_id: int | None = None
    weekday: int | None = Field(default=None, ge=0, le=6, description="0=Monday .. 6=Sunday")
    on_date: date | None = Field(default=None, alias="date")
    start_time: dtime
    end_time: dtime
    is_recurring: bool = True


class AvailabilityRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    clinic_id: int
    doctor_id: int | None
    service_id: int | None
    weekday: int | None
    date: date | None
    start_time: dtime
    end_time: dtime
    is_recurring: bool
    status: str


@router.get("", response_model=list[AvailabilityRead])
async def get_availability(
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return availability_service.list_availabilities(db, clinic)


@router.post("", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
async def post_availability(
    payload: AvailabilityCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    try:
        return availability_service.create_availability(
            db,
            clinic,
            doctor_id=payload.doctor_id,
            service_id=payload.service_id,
            weekday=payload.weekday,
            on_date=payload.on_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_recurring=payload.is_recurring,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/slots")
async def get_slots(
    on_date: date,
    doctor_id: int | None = None,
    service_id: int | None = None,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    slots = availability_service.free_slots(
        db,
        clinic,
        target_date=on_date,
        doctor_id=doctor_id,
        service_id=service_id,
    )
    return [s.isoformat() for s in slots]