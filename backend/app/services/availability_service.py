from datetime import date, datetime, time as dtime, timedelta

from sqlalchemy.orm import Session

from app.database.models import Appointment, Availability, Clinic, Doctor, Service
from app.services.doctor_service import get_doctor
from app.services.service_service import get_service

SLOT_STEP_MINUTES = 30


def create_availability(
    db: Session,
    clinic: Clinic,
    *,
    doctor_id: int | None = None,
    service_id: int | None = None,
    weekday: int | None = None,
    on_date: date | None = None,
    start_time: dtime,
    end_time: dtime,
    is_recurring: bool = True,
) -> Availability:
    if doctor_id is not None and get_doctor(db, clinic, doctor_id) is None:
        raise ValueError("Doctor not found")
    if service_id is not None and get_service(db, clinic, service_id) is None:
        raise ValueError("Service not found")
    if weekday is None and on_date is None:
        raise ValueError("Provide either a weekday or a date")

    availability = Availability(
        clinic_id=clinic.id,
        doctor_id=doctor_id,
        service_id=service_id,
        weekday=weekday,
        date=on_date,
        start_time=start_time,
        end_time=end_time,
        is_recurring=is_recurring,
    )
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


def list_availabilities(db: Session, clinic: Clinic) -> list[Availability]:
    return (
        db.query(Availability)
        .filter(Availability.clinic_id == clinic.id)
        .order_by(Availability.weekday, Availability.start_time)
        .all()
    )


def _matching_windows(db: Session, clinic: Clinic, target_date: date) -> list[Availability]:
    rows = db.query(Availability).filter(Availability.clinic_id == clinic.id).all()
    return [
        a
        for a in rows
        if a.status == "available"
        and (
            (a.is_recurring and a.weekday is not None and a.weekday == target_date.weekday())
            or (not a.is_recurring and a.date == target_date)
        )
    ]


def _appointment_conflicts(
    db: Session,
    clinic: Clinic,
    start: datetime,
    end: datetime,
    *,
    doctor_id: int | None,
    service_id: int | None,
) -> bool:
    query = db.query(Appointment).filter(
        Appointment.clinic_id == clinic.id,
        Appointment.status != "cancelled",
    )
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    elif service_id is not None:
        query = query.filter(Appointment.service_id == service_id)

    appointments = query.all()
    for appointment in appointments:
        if appointment.scheduled_at is None:
            continue
        if start < appointment.scheduled_at + timedelta(minutes=59) and appointment.scheduled_at < end:
            return True
    return False


def free_slots(
    db: Session,
    clinic: Clinic,
    *,
    target_date: date,
    doctor_id: int | None = None,
    service_id: int | None = None,
    step_minutes: int = SLOT_STEP_MINUTES,
) -> list[datetime]:
    """Return concrete open datetime slots for a given day (build plan 5.5 check_availability)."""
    doctor = get_doctor(db, clinic, doctor_id) if doctor_id else None
    service = get_service(db, clinic, service_id) if service_id else None
    if doctor is None and doctor_id is not None:
        return []
    if service is None and service_id is not None:
        return []

    duration = service.duration_minutes if service else 30
    windows = _matching_windows(db, clinic, target_date)

    now = datetime.now()
    slots: list[datetime] = []
    for window in windows:
        if window.doctor_id is not None and doctor_id is not None and window.doctor_id != doctor_id:
            continue
        if window.service_id is not None and service_id is not None and window.service_id != service_id:
            # A service-specific window takes precedence; ignore this window otherwise
            continue

        cursor = datetime.combine(target_date, window.start_time)
        end = datetime.combine(target_date, window.end_time)
        while cursor + timedelta(minutes=duration) <= end:
            if cursor > now:
                slot_end = cursor + timedelta(minutes=duration)
                if not _appointment_conflicts(
                    db, clinic, cursor, slot_end, doctor_id=doctor_id, service_id=service_id
                ):
                    slots.append(cursor)
            cursor += timedelta(minutes=step_minutes)

    # Deduplicate and sort
    unique = {s.isoformat(): s for s in slots}
    return sorted(unique.values())


def format_slots(slots: list[datetime]) -> list[str]:
    return [s.strftime("%Y-%m-%d %H:%M") for s in slots]


def parse_slot(slot_str: str) -> datetime:
    return datetime.fromisoformat(slot_str)