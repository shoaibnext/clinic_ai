from sqlalchemy.orm import Session

from app.database.models import Clinic, Doctor, DoctorService


def list_doctors(db: Session, clinic: Clinic, include_inactive: bool = False) -> list[Doctor]:
    query = db.query(Doctor).filter(Doctor.clinic_id == clinic.id)
    if not include_inactive:
        query = query.filter(Doctor.is_active.is_(True))
    return query.order_by(Doctor.name).all()


def get_doctor(db: Session, clinic: Clinic, doctor_id: int) -> Doctor | None:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None or doctor.clinic_id != clinic.id:
        return None
    return doctor


def create_doctor(
    db: Session,
    clinic: Clinic,
    *,
    name: str,
    title: str | None = None,
    specialty: str | None = None,
    bio: str | None = None,
    service_ids: list[int] | None = None,
) -> Doctor:
    doctor = Doctor(
        clinic_id=clinic.id,
        name=name,
        title=title,
        specialty=specialty,
        bio=bio,
    )
    db.add(doctor)
    db.flush()

    for service_id in service_ids or []:
        db.add(
            DoctorService(
                clinic_id=clinic.id,
                doctor_id=doctor.id,
                service_id=service_id,
            )
        )
    db.commit()
    db.refresh(doctor)
    return doctor