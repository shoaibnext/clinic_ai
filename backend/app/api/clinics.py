from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.clinic import ClinicCreate, ClinicOnboardResponse, ClinicRead
from app.services import clinic_service

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.post("", response_model=ClinicOnboardResponse, status_code=status.HTTP_201_CREATED)
async def onboard_clinic(payload: ClinicCreate, db: Session = Depends(get_db)):
    """Onboarding: create a clinic + first admin user. Returns the clinic API key once."""
    try:
        clinic = clinic_service.create_clinic(
            db,
            name=payload.name,
            slug=payload.slug,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            timezone=payload.timezone,
            admin_email=payload.admin_email,
            admin_password=payload.admin_password,
            whatsapp_phone_number_id=payload.whatsapp_phone_number_id,
            emergency_instructions=payload.emergency_instructions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ClinicOnboardResponse(
        **{**ClinicRead.model_validate(clinic).model_dump(), "api_key": clinic.api_key or ""}
    )


@router.get("/me", response_model=ClinicRead)
async def get_my_clinic(clinic: Clinic = Depends(get_current_clinic)):
    return clinic


@router.post("/{clinic_id}/whatsapp-phone", response_model=ClinicRead)
async def set_whatsapp_phone(
    clinic_id: int, phone_number_id: str, db: Session = Depends(get_db)
):
    clinic = clinic_service.get_clinic(db, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")
    clinic.whatsapp_phone_number_id = phone_number_id
    db.commit()
    db.refresh(clinic)
    return clinic