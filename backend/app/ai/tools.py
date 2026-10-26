"""Controlled backend tools the AI is allowed to request (build plan 5.5).

The LLM decides what the user means; the backend decides what is true and what
actions are allowed. Every mutation runs through a validated service function.
"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.database.models import Appointment, Clinic, Conversation, Doctor, Service
from app.services import appointment_service, availability_service, lead_service
from app.services.conversation_service import set_status
from app.services.doctor_service import get_doctor, list_doctors
from app.services.service_service import list_services


def get_doctors(db: Session, clinic: Clinic) -> list[Doctor]:
    return list_doctors(db, clinic)


def get_services(db: Session, clinic: Clinic, doctor_id: int | None = None) -> list[Service]:
    if doctor_id is not None and get_doctor(db, clinic, doctor_id) is not None:
        from app.services.service_service import services_for_doctor

        return services_for_doctor(db, clinic, doctor_id)
    return list_services(db, clinic)


def check_availability(
    db: Session,
    clinic: Clinic,
    *,
    on_date: date,
    doctor_id: int | None = None,
    service_id: int | None = None,
) -> list[datetime]:
    return availability_service.free_slots(
        db,
        clinic,
        target_date=on_date,
        doctor_id=doctor_id,
        service_id=service_id,
    )


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
) -> Appointment:
    return appointment_service.create_appointment(
        db,
        clinic,
        patient_id=patient_id,
        service_id=service_id,
        doctor_id=doctor_id,
        service_label=service_label,
        scheduled_at=scheduled_at,
        source=source,
    )


def get_appointment(db: Session, clinic: Clinic, appointment_id: int) -> Appointment | None:
    return appointment_service.get_appointment(db, clinic, appointment_id)


def cancel_appointment(db: Session, clinic: Clinic, appointment_id: int) -> Appointment | None:
    return appointment_service.cancel_appointment(db, clinic, appointment_id)


def reschedule_appointment(
    db: Session, clinic: Clinic, appointment_id: int, new_scheduled_at: datetime
) -> Appointment | None:
    return appointment_service.update_appointment(
        db, clinic, appointment_id, scheduled_at=new_scheduled_at
    )


def create_lead(db: Session, clinic: Clinic, **fields) -> object:
    return lead_service.create_lead(db, clinic, **fields)


def handoff_to_human(db: Session, clinic: Clinic, conversation: Conversation, reason: str | None = None) -> Conversation:
    return set_status(db, clinic, conversation.id, "human_requested")


# Descriptions exposed to the LLM so it knows what the backend can do.
TOOL_LIST = [
    {"name": "search_knowledge_base", "description": "Search the clinic's uploaded documents for an answer."},
    {"name": "get_doctors", "description": "List the clinic's doctors."},
    {"name": "get_services", "description": "List the clinic's services."},
    {"name": "check_availability", "description": "Return open appointment slots for a doctor/service on a date."},
    {"name": "create_appointment", "description": "Create and confirm an appointment after availability validation."},
    {"name": "get_appointment", "description": "Fetch an existing appointment by id."},
    {"name": "cancel_appointment", "description": "Cancel an existing appointment."},
    {"name": "reschedule_appointment", "description": "Move an existing appointment to a new slot."},
    {"name": "create_lead", "description": "Save a prospective patient as a lead."},
    {"name": "handoff_to_human", "description": "Escalate the conversation to clinic staff."},
]