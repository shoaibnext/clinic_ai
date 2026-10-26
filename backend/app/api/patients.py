from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead])
async def get_patients(clinic: Clinic = Depends(get_current_clinic), db: Session = Depends(get_db)):
    return patient_service.list_patients(db, clinic)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_single_patient(
    patient_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    patient = patient_service.get_patient(db, clinic, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def post_patient(
    payload: PatientCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    if patient_service.get_patient_by_phone(db, clinic, payload.phone_number) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient with this phone number already exists",
        )
    return patient_service.create_patient(
        db,
        clinic,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        language=payload.language,
        email=payload.email,
    )


@router.patch("/{patient_id}", response_model=PatientRead)
async def patch_patient(
    patient_id: int,
    payload: PatientUpdate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    try:
        patient = patient_service.update_patient(
            db,
            clinic,
            patient_id,
            full_name=payload.full_name,
            phone_number=payload.phone_number,
            email=payload.email,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_single_patient(
    patient_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    deleted = patient_service.delete_patient(db, clinic, patient_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")