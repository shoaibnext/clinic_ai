from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.service import ServiceCreate, ServiceRead
from app.services import service_service

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceRead])
async def get_services(
    doctor_id: int | None = Query(default=None),
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    if doctor_id is not None:
        return service_service.services_for_doctor(db, clinic, doctor_id)
    return service_service.list_services(db, clinic)


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def post_service(
    payload: ServiceCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return service_service.create_service(
        db,
        clinic,
        name=payload.name,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        doctor_ids=payload.doctor_ids,
    )


@router.get("/{service_id}", response_model=ServiceRead)
async def get_single_service(
    service_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    service = service_service.get_service(db, clinic, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service