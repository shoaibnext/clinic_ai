from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.services import appointment_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentRead])
async def get_appointments(
    patient_id: int | None = Query(default=None),
    doctor_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    upcoming: bool = Query(default=False),
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return appointment_service.list_appointments(
        db,
        clinic,
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=status_filter,
        upcoming_only=upcoming,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_single_appointment(
    appointment_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    appointment = appointment_service.get_appointment(db, clinic, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def post_appointment(
    payload: AppointmentCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    try:
        return appointment_service.create_appointment(
            db,
            clinic,
            patient_id=payload.patient_id,
            service_id=payload.service_id,
            doctor_id=payload.doctor_id,
            service_label=payload.service_label,
            scheduled_at=payload.scheduled_at,
            source=payload.source,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def patch_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    try:
        appointment = appointment_service.update_appointment(
            db,
            clinic,
            appointment_id,
            status=payload.status,
            scheduled_at=payload.scheduled_at,
            doctor_id=payload.doctor_id,
            service_id=payload.service_id,
            service_label=payload.service_label,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_single_appointment(
    appointment_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    cancelled = appointment_service.cancel_appointment(db, clinic, appointment_id)
    if cancelled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")