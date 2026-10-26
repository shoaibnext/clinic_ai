from sqlalchemy.orm import Session

from app.database.models import Clinic, DoctorService, Service


def list_services(db: Session, clinic: Clinic, include_inactive: bool = False) -> list[Service]:
    query = db.query(Service).filter(Service.clinic_id == clinic.id)
    if not include_inactive:
        query = query.filter(Service.is_active.is_(True))
    return query.order_by(Service.name).all()


def get_service(db: Session, clinic: Clinic, service_id: int) -> Service | None:
    service = db.get(Service, service_id)
    if service is None or service.clinic_id != clinic.id:
        return None
    return service


def create_service(
    db: Session,
    clinic: Clinic,
    *,
    name: str,
    description: str | None = None,
    duration_minutes: int = 30,
    price: str | None = None,
    doctor_ids: list[int] | None = None,
) -> Service:
    service = Service(
        clinic_id=clinic.id,
        name=name,
        description=description,
        duration_minutes=duration_minutes,
        price=price,
    )
    db.add(service)
    db.flush()

    for doctor_id in doctor_ids or []:
        db.add(
            DoctorService(
                clinic_id=clinic.id,
                doctor_id=doctor_id,
                service_id=service.id,
            )
        )
    db.commit()
    db.refresh(service)
    return service


def services_for_doctor(db: Session, clinic: Clinic, doctor_id: int) -> list[Service]:
    rows = (
        db.query(DoctorService)
        .filter(
            DoctorService.clinic_id == clinic.id,
            DoctorService.doctor_id == doctor_id,
        )
        .all()
    )
    service_ids = [r.service_id for r in rows]
    if not service_ids:
        return []
    return db.query(Service).filter(Service.id.in_(service_ids), Service.is_active.is_(True)).all()