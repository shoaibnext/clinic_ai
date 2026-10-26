"""Idempotent dev-seed script: create a demo clinic with an admin user.

Usage (from the backend/ directory):

    python scripts/seed_clinic.py            # uses defaults below
    python scripts/seed_clinic.py --email admin@demo.test --password Demo1234!

Re-running with the same slug (default: from --name) updates nothing and
prints the existing clinic's API key instead of creating a duplicate.
"""
import argparse
import os
import sys

from sqlalchemy.orm import Session

# Ensure the backend root is importable regardless of how the script is invoked
# (running `python scripts/seed_clinic.py` puts `scripts/` on sys.path, not `backend/`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database.database import SessionLocal, Base, engine
from app.services import clinic_service


def seed_clinic(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    phone: str | None,
    address: str | None,
    slug: str | None = None,
):
    if slug is None:
        slug = clinic_service.slugify(name)

    existing = clinic_service.get_clinic_by_slug(db, slug)
    if existing is not None:
        print(f"Clinic already exists: {existing.name} (id={existing.id}, slug={existing.slug})")
        print(f"API key: {existing.api_key}")
        return existing

    clinic = clinic_service.create_clinic(
        db,
        name=name,
        slug=slug,
        phone=phone,
        address=address,
        admin_email=email,
        admin_password=password,
    )
    print(f"Clinic created: {clinic.name} (id={clinic.id}, slug={clinic.slug})")
    print(f"Admin: {email}")
    print(f"API key: {clinic.api_key}")
    return clinic


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed a demo clinic for local development.")
    parser.add_argument("--name", default="ABC Dental Clinic")
    parser.add_argument("--slug", default=None, help="Optional slug; defaults to the slugified name.")
    parser.add_argument("--email", default="admin@gmail.com")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--phone", default="+923001234567")
    parser.add_argument("--address", default="123 Main Street, Karachi")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_clinic(
            db,
            name=args.name,
            slug=args.slug,
            email=args.email,
            password=args.password,
            phone=args.phone,
            address=args.address,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()