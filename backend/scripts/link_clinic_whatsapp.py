"""Link a WhatsApp phone-number-id to a clinic (used for webhook tenant routing).

The inbound webhook resolves the clinic by its `whatsapp_phone_number_id`.
Set it to the clinic's real Phone Number ID from Meta (WhatsApp -> API Setup).

Usage (from backend/):
    python scripts/link_clinic_whatsapp.py <phone_number_id> [clinic_slug]

Prints the first clinic if none matches the optional slug.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Clinic


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    phone_number_id = sys.argv[1].strip()
    slug = sys.argv[2].strip() if len(sys.argv) > 2 else None

    db: Session = SessionLocal()
    try:
        clinic = db.query(Clinic).filter(Clinic.slug == slug).first() if slug else db.query(Clinic).first()
        if clinic is None:
            clinics = db.query(Clinic).all()
            if not clinics:
                print("No clinics in the DB yet. Create one first:")
                print("  python scripts/seed_clinic.py   # or POST /clinics")
                return
            clinic = clinics[0]
        clinic.whatsapp_phone_number_id = phone_number_id
        db.commit()
        print(f"Linked clinic '{clinic.slug}' -> whatsapp_phone_number_id={phone_number_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()