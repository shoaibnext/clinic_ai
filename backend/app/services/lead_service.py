from sqlalchemy.orm import Session

from app.database.models import Clinic, Lead

VALID_STATUSES = {"new", "contacted", "converted", "lost"}


def list_leads(db: Session, clinic: Clinic, status: str | None = None) -> list[Lead]:
    query = db.query(Lead).filter(Lead.clinic_id == clinic.id)
    if status is not None:
        query = query.filter(Lead.status == status)
    return query.order_by(Lead.created_at.desc()).all()


def get_lead(db: Session, clinic: Clinic, lead_id: int) -> Lead | None:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.clinic_id != clinic.id:
        return None
    return lead


def create_lead(
    db: Session,
    clinic: Clinic,
    *,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    service: str | None = None,
    preferred_date: str | None = None,
    preferred_time: str | None = None,
    source: str = "whatsapp",
    notes: str | None = None,
) -> Lead:
    lead = Lead(
        clinic_id=clinic.id,
        name=name,
        phone=phone,
        email=email,
        service=service,
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        source=source,
        notes=notes,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, clinic: Clinic, lead_id: int, **fields) -> Lead | None:
    lead = get_lead(db, clinic, lead_id)
    if lead is None:
        return None
    status = fields.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")
    for key, value in fields.items():
        if value is not None:
            setattr(lead, key, value)
    db.commit()
    db.refresh(lead)
    return lead