from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.doctor import DoctorCreate, DoctorRead
from app.schemas.service import ServiceRead
from app.services import doctor_service, service_service

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorRead])
async def get_doctors(clinic: Clinic = Depends(get_current_clinic), db: Session = Depends(get_db)):
    return doctor_service.list_doctors(db, clinic)


@router.post("", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
async def post_doctor(
    payload: DoctorCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return doctor_service.create_doctor(
        db,
        clinic,
        name=payload.name,
        title=payload.title,
        specialty=payload.specialty,
        bio=payload.bio,
        service_ids=payload.service_ids,
    )


@router.get("/{doctor_id}", response_model=DoctorRead)
async def get_single_doctor(
    doctor_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    doctor = doctor_service.get_doctor(db, clinic, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


@router.get("/{doctor_id}/services", response_model=list[ServiceRead])
async def get_doctor_services(
    doctor_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    doctor = doctor_service.get_doctor(db, clinic, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return service_service.services_for_doctor(db, clinic, doctor_id)