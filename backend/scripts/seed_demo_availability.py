"""Idempotently seed a demo doctor/service/availability schedule for a clinic.

Clinics created through the admin UI often have no schedule set, so the
WhatsApp bot can never find slots ("no available slots"). This helper fills
the gap with a Mon-Fri 09:00-17:00 recurring schedule.

Usage (from backend/):
    python scripts/seed_demo_availability.py            # first clinic
    python scripts/seed_demo_availability.py --clinic-slug abc-dental-clinic
"""

import argparse
import pathlib
import sys
from datetime import time as dtime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.database.database import SessionLocal  # noqa: E402
from app.services import (  # noqa: E402
    availability_service,
    clinic_service,
    doctor_service,
    service_service,
)

WEEKDAYS = range(5)  # Monday .. Friday


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinic-slug", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.clinic_slug:
            clinic = clinic_service.get_clinic_by_slug(db, args.clinic_slug)
        else:
            clinics = clinic_service.list_clinics(db)
            clinic = clinics[0] if clinics else None
        if clinic is None:
            print("No clinic found. Create one first (scripts/seed_clinic.py or POST /clinics).")
            return 1

        doctors = doctor_service.list_doctors(db, clinic)
        if doctors:
            doctor = doctors[0]
        else:
            doctor = doctor_service.create_doctor(
                db, clinic, name="Dr. Demo", title="General", specialty="General"
            )
            print(f"Created doctor: {doctor.name}")

        services = service_service.list_services(db, clinic)
        if services:
            service = services[0]
        else:
            service = service_service.create_service(
                db, clinic, name="General Consultation", duration_minutes=30, price="1500"
            )
            print(f"Created service: {service.name}")

        existing = availability_service.list_availabilities(db, clinic)
        made = 0
        for weekday in WEEKDAYS:
            if any(a.weekday == weekday for a in existing):
                continue
            availability_service.create_availability(
                db,
                clinic,
                doctor_id=doctor.id,
                service_id=service.id,
                weekday=weekday,
                start_time=dtime(9, 0),
                end_time=dtime(17, 0),
                is_recurring=True,
            )
            made += 1

        print(
            f"Clinic '{clinic.slug}': doctor={doctor.name!r}, service={service.name!r}, "
            f"availability rows added={made}, total={len(existing) + made} (Mon-Fri 09:00-17:00)"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())