from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.lead import LeadCreate, LeadRead, LeadUpdate
from app.services import lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=list[LeadRead])
async def get_leads(
    status_filter: str | None = Query(default=None, alias="status"),
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return lead_service.list_leads(db, clinic, status=status_filter)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_single_lead(
    lead_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    lead = lead_service.get_lead(db, clinic, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def post_lead(
    payload: LeadCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return lead_service.create_lead(
        db,
        clinic,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        service=payload.service,
        preferred_date=payload.preferred_date,
        preferred_time=payload.preferred_time,
        source=payload.source,
        notes=payload.notes,
    )


@router.patch("/{lead_id}", response_model=LeadRead)
async def patch_lead(
    lead_id: int,
    payload: LeadUpdate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    try:
        lead = lead_service.update_lead(
            db,
            clinic,
            lead_id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            service=payload.service,
            status=payload.status,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead