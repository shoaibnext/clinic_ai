from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database.models import Appointment, Clinic, Patient
from app.services.availability_service import _appointment_conflicts
from app.services.doctor_service import get_doctor
from app.services.patient_service import get_patient
from app.services.service_service import get_service

VALID_STATUSES = {"scheduled", "cancelled", "completed"}


def list_appointments(
    db: Session,
    clinic: Clinic,
    *,
    patient_id: int | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
    upcoming_only: bool = False,
) -> list[Appointment]:
    query = db.query(Appointment).filter(Appointment.clinic_id == clinic.id)
    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if status is not None:
        query = query.filter(Appointment.status == status)
    if upcoming_only:
        query = query.filter(
            Appointment.status != "cancelled", Appointment.scheduled_at >= datetime.now()
        )
    return query.order_by(Appointment.scheduled_at.asc()).all()


def get_appointment(db: Session, clinic: Clinic, appointment_id: int) -> Appointment | None:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.clinic_id != clinic.id:
        return None
    return appointment


def create_appointment(
    db: Session,
    clinic: Clinic,
    *,
    patient_id: int,
    service_id: int | None = None,
    doctor_id: int | None = None,
    service_label: str | None = None,
    scheduled_at: datetime | None = None,
    source: str = "whatsapp",
    notes: str | None = None,
) -> Appointment:
    patient = get_patient(db, clinic, patient_id)
    if patient is None:
        raise ValueError("Patient not found")
    if service_id is not None and get_service(db, clinic, service_id) is None:
        raise ValueError("Service not found")
    if doctor_id is not None and get_doctor(db, clinic, doctor_id) is None:
        raise ValueError("Doctor not found")

    service = get_service(db, clinic, service_id) if service_id else None
    label = service_label or (service.name if service else None)

    if scheduled_at is not None:
        if scheduled_at <= datetime.now():
            raise ValueError("Appointment must be in the future")
        duration = service.duration_minutes if service else 30
        if _appointment_conflicts(
            db,
            clinic,
            scheduled_at,
            scheduled_at + timedelta(minutes=duration),
            doctor_id=doctor_id,
            service_id=service_id,
        ):
            raise ValueError("Requested time is no longer available")

    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient_id,
        service_id=service_id,
        doctor_id=doctor_id,
        service_label=label,
        scheduled_at=scheduled_at,
        status="scheduled",
        source=source,
        notes=notes,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def update_appointment(db: Session, clinic: Clinic, appointment_id: int, **fields) -> Appointment | None:
    appointment = get_appointment(db, clinic, appointment_id)
    if appointment is None:
        return None

    status = fields.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")

    new_scheduled_at = fields.get("scheduled_at")
    if new_scheduled_at is not None:
        if new_scheduled_at <= datetime.now():
            raise ValueError("Appointment must be in the future")
        service = get_service(db, clinic, appointment.service_id) if appointment.service_id else None
        duration = service.duration_minutes if service else 30
        if _appointment_conflicts(
            db,
            clinic,
            new_scheduled_at,
            new_scheduled_at + timedelta(minutes=duration),
            doctor_id=fields.get("doctor_id", appointment.doctor_id),
            service_id=fields.get("service_id", appointment.service_id),
        ):
            raise ValueError("Requested time is no longer available")

    for key, value in fields.items():
        if value is not None:
            setattr(appointment, key, value)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, clinic: Clinic, appointment_id: int) -> Appointment | None:
    appointment = get_appointment(db, clinic, appointment_id)
    if appointment is None:
        return None
    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)
    return appointment


def upcoming_appointments(db: Session, clinic: Clinic, patient_id: int) -> list[Appointment]:
    return list_appointments(
        db, clinic, patient_id=patient_id, status="scheduled", upcoming_only=True
    )