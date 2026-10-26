from sqlalchemy.orm import Session

from app.database.models import Clinic, Patient


def list_patients(db: Session, clinic: Clinic) -> list[Patient]:
    return db.query(Patient).filter(Patient.clinic_id == clinic.id).order_by(Patient.created_at.desc()).all()


def get_patient(db: Session, clinic: Clinic, patient_id: int) -> Patient | None:
    patient = db.get(Patient, patient_id)
    if patient is None or patient.clinic_id != clinic.id:
        return None
    return patient


def get_patient_by_phone(db: Session, clinic: Clinic, phone_number: str) -> Patient | None:
    return (
        db.query(Patient)
        .filter(Patient.clinic_id == clinic.id, Patient.phone_number == phone_number)
        .first()
    )


def get_or_create_patient(
    db: Session, clinic: Clinic, phone_number: str, language: str = "en"
) -> Patient:
    patient = get_patient_by_phone(db, clinic, phone_number)
    if patient is None:
        patient = Patient(clinic_id=clinic.id, full_name="", phone_number=phone_number, language=language)
        db.add(patient)
        db.commit()
        db.refresh(patient)
    elif patient.language != language:
        patient.language = language
        db.commit()
        db.refresh(patient)
    return patient


def create_patient(
    db: Session, clinic: Clinic, *, full_name: str = "", phone_number: str, language: str = "en", email: str | None = None
) -> Patient:
    if get_patient_by_phone(db, clinic, phone_number) is not None:
        raise ValueError("Patient with this phone number already exists")
    patient = Patient(
        clinic_id=clinic.id,
        full_name=full_name,
        phone_number=phone_number,
        language=language,
        email=email,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, clinic: Clinic, patient_id: int, **fields) -> Patient | None:
    patient = get_patient(db, clinic, patient_id)
    if patient is None:
        return None
    new_phone = fields.get("phone_number")
    if new_phone is not None and new_phone != patient.phone_number:
        duplicate = (
            db.query(Patient)
            .filter(
                Patient.clinic_id == clinic.id,
                Patient.phone_number == new_phone,
                Patient.id != patient_id,
            )
            .first()
        )
        if duplicate is not None:
            raise ValueError("Patient with this phone number already exists")
    for key, value in fields.items():
        if value is not None:
            setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


def delete_patient(db: Session, clinic: Clinic, patient_id: int) -> bool:
    patient = get_patient(db, clinic, patient_id)
    if patient is None:
        return False
    db.delete(patient)
    db.commit()
    return True