"""Interactive fake-patient simulator for the real WhatsApp webhook.

Sends Meta-shaped payloads to the REAL ``POST /whatsapp/webhook`` endpoint
(in-process TestClient), which then runs the REAL receptionist loop: clinic/
patient/conversation resolution, AI orchestration (intent -> RAG -> tools ->
validation) and persistence in the REAL database. The AI reply is read back
from the database (the same source of truth the real webhook writes to), so
this is not a fake chatbot UI — the only simulated layer is the WhatsApp
transport (Meta Graph -> this script; swap in ngrok + real Meta later).

Usage (from the backend/ directory):

    python scripts/whatsapp_simulator.py                     # first available clinic
    python scripts/whatsapp_simulator.py --clinic abc-dental
    python scripts/whatsapp_simulator.py --phone +15550101111 --seed
    python scripts/whatsapp_simulator.py --one "I want to book a dental cleaning"
    python scripts/whatsapp_simulator.py --send              # ALSO post replies to real Meta

By default no real WhatsApp messages are sent: the outbound Meta credentials
are blanked for each request unless --send is given. If WHATSAPP_APP_SECRET is
configured, every simulated request is signed with X-Hub-Signature-256 exactly
like Meta does.
"""

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import sys

# Ensure the backend root is importable (scripts/ is on sys.path when run directly).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_PHONE = "+15550101111"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a patient on the real WhatsApp webhook.")
    parser.add_argument("--clinic", default=None, help="Clinic slug to talk to (default: newest clinic)")
    parser.add_argument("--phone", default=DEFAULT_PHONE, help="Simulated patient phone number")
    parser.add_argument(
        "--db",
        default=None,
        help="Database to use (path or DSN). Default: whatever the app is configured with (.env DATABASE_URL)",
    )
    parser.add_argument(
        "--seed", action="store_true", help="Create the demo ABC Dental Clinic first if it doesn't exist"
    )
    parser.add_argument(
        "--send", action="store_true", help="Also send replies through the real Meta WhatsApp API"
    )
    parser.add_argument("--one", metavar="MESSAGE", default=None, help="Send one message and exit")
    return parser.parse_args()


def _seed_demo_clinic(db) -> object | None:
    from datetime import time as dtime

    from app.services import availability_service, clinic_service, doctor_service, service_service

    existing = clinic_service.get_clinic_by_slug(db, "abc-dental")
    if existing is not None:
        print(f"Demo clinic already exists: {existing.name} (slug={existing.slug})")
    else:
        existing = clinic_service.create_clinic(
            db,
            name="ABC Dental Clinic",
            slug="abc-dental",
            phone="+923001234567",
            address="123 Main Street, Karachi",
            admin_email="admin@gmail.com",
            admin_password="admin123",
        )
        print(f"Created demo clinic: {existing.name} (slug={existing.slug}) -> api key: {existing.api_key}")

    # Minimal demo catalog so the booking flow has something to book
    # (service -> date -> time -> confirm). All idempotent.
    service = service_service.list_services(db, existing)[0] if service_service.list_services(
        db, existing
    ) else None
    if service is None:
        service = service_service.create_service(
            db, existing, name="Dental Cleaning", duration_minutes=30, price="1500"
        )
        print(f"Created demo service: {service.name} ({service.duration_minutes} min)")
    doctor = doctor_service.list_doctors(db, existing)[0] if doctor_service.list_doctors(
        db, existing
    ) else None
    if doctor is None:
        doctor = doctor_service.create_doctor(
            db,
            existing,
            name="Dr. Khan",
            title="Dentist",
            specialty="Dentistry",
            service_ids=[service.id],
        )
        print(f"Created demo doctor: {doctor.name} ({doctor.title})")
    if not availability_service.list_availabilities(db, existing):
        availability_service.create_availability(
            db,
            existing,
            doctor_id=doctor.id,
            service_id=service.id,
            weekday=0,
            start_time=dtime(9, 0),
            end_time=dtime(17, 0),
            is_recurring=True,
        )
        print("Created recurring availability: Mon-Fri 09:00-17:00")
    return existing


def _resolve_clinic(db, args: argparse.Namespace):
    from app.services import clinic_service

    if args.clinic:
        clinic = clinic_service.get_clinic_by_slug(db, args.clinic)
        if clinic is None:
            print(f"!! No clinic found with slug {args.clinic!r}. Available clinics:")
            for existing in clinic_service.list_clinics(db):
                print(f"   slug={existing.slug!r}  name={existing.name!r}")
            return None
    else:
        clinics = clinic_service.list_clinics(db)
        if not clinics:
            print("!! No clinics in the database. Create one first:")
            print("   python scripts/seed_clinic.py")
            print("   or re-run with --seed")
            return None
        clinic = clinics[0]

    # The webhook resolves the clinic by metadata.phone_number_id. A real deploy
    # must set this on the clinic, so mirror that here (with a stable sim id) to
    # guarantee we talk to the clinic the user asked for.
    if not clinic.whatsapp_phone_number_id:
        synthetic = f"sim-{clinic.slug}"
        clinic.whatsapp_phone_number_id = synthetic
        db.commit()
        print(
            f"!! Clinic {clinic.slug!r} had no WhatsApp phone-number-id; set it to {synthetic!r} "
            "so the webhook can resolve this clinic (mirrors the real Meta config step)."
        )
    return clinic


def _build_payload(*, phone_number_id: str, phone: str, message_id: str, text: str) -> dict:
    """Meta WhatsApp Cloud API webhook payload (same shape as WhatsApp sends)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "sim-entry",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"wa_id": phone}],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@contextlib.contextmanager
def _no_meta_send(enabled: bool):
    """Blank outbound WhatsApp creds unless --send, so no accidental real sends."""
    from app.core.config import settings

    if enabled:
        yield
        return
    original_id = settings.whatsapp_phone_number_id
    original_token = settings.whatsapp_access_token
    settings.whatsapp_phone_number_id = ""
    settings.whatsapp_access_token = ""
    try:
        yield
    finally:
        settings.whatsapp_phone_number_id = original_id
        settings.whatsapp_access_token = original_token


def _post_webhook(client, payload: dict) -> tuple[int, str]:
    """POST the payload to the real endpoint, signing it like Meta does."""
    from app.core.config import settings

    body = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json"}
    if settings.whatsapp_app_secret:
        digest = hmac.new(
            settings.whatsapp_app_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        headers["X-Hub-Signature-256"] = f"sha256={digest}"
    response = client.post("/whatsapp/webhook", content=body, headers=headers)
    return response.status_code, response.text


def _fetch_ai_reply(db, clinic, phone: str) -> str:
    """Read the persisted AI reply for this patient's active conversation.

    The webhook endpoint persists the outbound reply and returns only
    {"status": "ok"} (like real WhatsApp), so the reply is read back from the
    database — the same source of truth used everywhere else.
    """
    from app.database.models import Conversation, Message
    from app.services import patient_service

    patient = patient_service.get_patient_by_phone(db, clinic, phone)
    if patient is None:
        return "!! (no patient row was created)"
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.clinic_id == clinic.id,
            Conversation.patient_id == patient.id,
            Conversation.status != "resolved",
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if conversation is None:
        return "!! (no conversation was created)"
    last_out = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.direction == "out")
        .order_by(Message.id.desc())
        .first()
    )
    if last_out is None:
        return "!! (no outbound reply was persisted — did the AI step fail?)"
    return last_out.body


def _banner(clinic, args: argparse.Namespace) -> None:
    from app.core.config import settings

    signature = (
        "ON (X-Hub-Signature-256)" if settings.whatsapp_app_secret else "OFF (no WHATSAPP_APP_SECRET set)"
    )
    outbound = "ENABLED (--send)" if args.send else "disabled (use --send to enable)"
    print("\n" + "=" * 64)
    print("  WhatsApp webhook simulator  (fake patient -> real endpoint -> real AI -> real DB)")
    print("=" * 64)
    print(f"  Clinic : {clinic.name!r} (slug={clinic.slug})")
    print(f"  Patient: {args.phone}")
    print(f"  Number-id: {clinic.whatsapp_phone_number_id}")
    print(f"  Signature check : {signature}")
    print(f"  Real Meta sends : {outbound}")
    print("  Type a message and press Enter. 'quit' exits.\n")


def _post_and_reply(client, db, clinic, args: argparse.Namespace, message_id: str, text: str) -> str:
    payload = _build_payload(
        phone_number_id=clinic.whatsapp_phone_number_id,
        phone=args.phone,
        message_id=message_id,
        text=text,
    )
    with _no_meta_send(args.send):
        status, body = _post_webhook(client, payload)
    if status != 200:
        return f"!! webhook returned HTTP {status}: {body[:300]}"
    # The endpoint committed its writes on its own connection; end our read
    # transaction so the Conversation/Message query below sees the fresh rows.
    db.rollback()
    return _fetch_ai_reply(db, clinic, args.phone)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console
    except Exception:
        pass

    args = _parse_args()
    if args.db:
        database_url = args.db if "://" in args.db else f"sqlite:///./{args.db}"
        os.environ["DATABASE_URL"] = database_url  # must be set before importing app

    from fastapi.testclient import TestClient

    from app.database.database import SessionLocal
    from app.main import app

    db = SessionLocal()
    try:
        if args.seed:
            _seed_demo_clinic(db)
        clinic = _resolve_clinic(db, args)
        if clinic is None:
            return 1
        _banner(clinic, args)

        # raise_server_exceptions=False: a provider failure surfaces as a normal
        # HTTP 500 response (shown cleanly below) instead of crashing the REPL.
        with TestClient(app, raise_server_exceptions=False) as client:
            if args.one:
                reply = _post_and_reply(
                    client, db, clinic, args, f"wamid.sim.{os.getpid()}.0", args.one
                )
                print(f"You: {args.one}\nAI: {reply}")
                return 0

            seq = 0
            while True:
                try:
                    text = input("You: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    break
                if not text:
                    continue
                if text.lower() in ("quit", "exit", "/quit"):
                    break
                seq += 1
                reply = _post_and_reply(
                    client, db, clinic, args, f"wamid.sim.{os.getpid()}.{seq}", text
                )
                print(f"AI: {reply}")
            print("Bye.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())