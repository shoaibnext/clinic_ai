import re
import secrets

from sqlalchemy.orm import Session

from app.database.models import Clinic, User
from app.services.auth_service import create_user


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "clinic"


def generate_api_key() -> str:
    return f"ck_{secrets.token_urlsafe(32)}"


def create_clinic(
    db: Session,
    *,
    name: str,
    slug: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    timezone: str = "Asia/Karachi",
    admin_email: str | None = None,
    admin_password: str | None = None,
    whatsapp_phone_number_id: str | None = None,
    emergency_instructions: str | None = None,
) -> Clinic:
    slug = slugify(slug or name)
    if db.query(Clinic).filter(Clinic.slug == slug).first():
        raise ValueError(f"Clinic slug '{slug}' is already in use")

    clinic = Clinic(
        name=name,
        slug=slug,
        phone=phone,
        email=email,
        address=address,
        timezone=timezone,
        api_key=generate_api_key(),
        whatsapp_phone_number_id=whatsapp_phone_number_id,
        emergency_instructions=emergency_instructions,
    )
    db.add(clinic)
    db.flush()

    if admin_email and admin_password:
        create_user(
            db,
            clinic_id=clinic.id,
            email=admin_email,
            password=admin_password,
            full_name="Clinic Admin",
            role="admin",
        )

    db.commit()
    db.refresh(clinic)
    return clinic


def get_clinic(db: Session, clinic_id: int) -> Clinic | None:
    return db.get(Clinic, clinic_id)


def get_clinic_by_slug(db: Session, slug: str) -> Clinic | None:
    return db.query(Clinic).filter(Clinic.slug == slug).first()


def get_clinic_by_api_key(db: Session, api_key: str) -> Clinic | None:
    return db.query(Clinic).filter(Clinic.api_key == api_key).first()


def get_clinic_by_whatsapp_phone(db: Session, phone_number_id: str) -> Clinic | None:
    if not phone_number_id:
        return None
    return db.query(Clinic).filter(Clinic.whatsapp_phone_number_id == phone_number_id).first()


def list_clinics(db: Session) -> list[Clinic]:
    return db.query(Clinic).order_by(Clinic.created_at.desc()).all()