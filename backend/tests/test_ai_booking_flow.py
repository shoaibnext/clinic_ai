"""Full AI receptionist booking loop (build plan 5.2 / 5.13) with a mocked LLM.

The intent extractor and answer generator are replaced with deterministic fakes so
the test exercises the real orchestrator flow: intent -> state -> availability tool
-> name collection -> confirmation -> create appointment tool -> validation.
"""
import json
from datetime import date, datetime, time, timedelta

import pytest

from app.ai.orchestrator import handle_message
from app.services import conversation_service, patient_service

_PENDING_ENTITIES = {
    "service": None,
    "doctor": None,
    "date": None,
    "time": None,
    "patient_name": None,
}


def _intent_json(intent: str, confidence: float, **entity_overrides) -> str:
    entities = dict(_PENDING_ENTITIES)
    entities.update({k: v for k, v in entity_overrides.items() if v is not None})
    return json.dumps({"intent": intent, "confidence": confidence, "entities": entities})


def _next_monday() -> str:
    today = date.today()
    delta = (0 - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return (today + timedelta(days=delta)).isoformat()


def _booking_intent_fake():
    """Return (fake_complete, monday_date_string) scripting the booking conversation."""
    monday = _next_monday()

    async def fake_complete(messages, **kwargs):
        last = messages[-1]["content"].lower()
        # Initial booking request: extract service + date.
        if "dental cleaning" in last and monday in last:
            return _intent_json(
                "BOOK_APPOINTMENT", 0.97, service="Dental Cleaning", date=monday
            )
        # Patient supplies their name.
        if last == "my name is ali":
            return _intent_json("PROVIDE_PATIENT_INFO", 0.95, patient_name="Ali")
        # Any other (time picker, confirmation, reschedule) message stays on booking.
        return _intent_json("BOOK_APPOINTMENT", 0.9)

    return fake_complete, monday


async def _turn(monkeypatch, db, clinic, conversation, patient, message):
    fake_complete, _ = _booking_intent_fake()
    monkeypatch.setattr("app.ai.intent.complete", fake_complete)
    reply = await handle_message(
        db, clinic=clinic, patient=patient, conversation=conversation, user_message=message
    )
    db.commit()
    return reply

@pytest.mark.asyncio
async def test_human_handoff_escalates(db_session, clinic, patient, monkeypatch):
    fake_complete, _ = _booking_intent_fake()
    monkeypatch.setattr("app.ai.intent.complete", fake_complete)

    conversation = conversation_service.get_or_create_conversation(
        db_session, clinic, patient, channel="whatsapp"
    )
    reply = await _turn(
        monkeypatch, db_session, clinic, conversation, patient,
        "I want to speak to a human please",
    )
    assert "staff" in reply.lower() or "receptionist" in reply.lower()
    assert conversation.status == "human_requested"


@pytest.mark.asyncio
async def test_emergency_triggers_handoff(db_session, clinic, patient, monkeypatch):
    fake_complete, _ = _booking_intent_fake()
    monkeypatch.setattr("app.ai.intent.complete", fake_complete)

    conversation = conversation_service.get_or_create_conversation(
        db_session, clinic, patient, channel="whatsapp"
    )
    reply = await _turn(
        monkeypatch, db_session, clinic, conversation, patient,
        "i have severe chest pain",
    )
    assert "emergency" in reply.lower()
    assert conversation.status == "human_requested"


@pytest.mark.asyncio
async def test_reschedule_smoke(db_session, clinic, patient, doctor, service, availability, monkeypatch):
    fake_complete, monday = _booking_intent_fake()
    monkeypatch.setattr("app.ai.intent.complete", fake_complete)

    from app.services.appointment_service import create_appointment

    first_day = date.today() + timedelta(days=30)
    create_appointment(
        db_session,
        clinic,
        patient_id=patient.id,
        service_id=service.id,
        doctor_id=doctor.id,
        scheduled_at=datetime.combine(first_day, time(10, 0)),
    )
    conversation = conversation_service.get_or_create_conversation(
        db_session, clinic, patient, channel="whatsapp"
    )
    reply = await _turn(
        monkeypatch, db_session, clinic, conversation, patient,
        f"I want to reschedule to {monday}",
    )
    assert "Which time would you like?" in reply or "available" in reply.lower()
    assert conversation.status == "ai_active"


def test_ai_events_recorded(db_session, clinic, patient):
    """record_ai_event persists without breaking the flow."""
    from app.ai.events import record_ai_event
    from app.database.models import AIEvent

    record_ai_event(
        db_session,
        clinic_id=clinic.id,
        conversation_id=None,
        event_type="tool_call",
        input_data={"tool": "check_availability"},
    )
    db_session.commit()
    rows = db_session.query(AIEvent).all()
    assert len(rows) == 1
    assert rows[0].event_type == "tool_call"

@pytest.mark.asyncio
async def test_booking_loop_end_to_end(db_session, clinic, service, doctor, availability, monkeypatch):
    fake_complete, monday = _booking_intent_fake()
    monkeypatch.setattr("app.ai.intent.complete", fake_complete)

    patient = patient_service.create_patient(db_session, clinic, phone_number="+15550108888")
    conversation = conversation_service.get_or_create_conversation(
        db_session, clinic, patient, channel="whatsapp"
    )

    # 1. Booking intent + entity extraction -> availability offered -> asks for a time.
    reply = await _turn(monkeypatch, db_session, clinic, conversation, patient,
                        f"i want to book a dental cleaning on {monday}")
    assert "Which time works for you?" in reply

    # 2. User picks the first offered slot (bare number) -> now asks for the name.
    reply = await _turn(monkeypatch, db_session, clinic, conversation, patient, "1")
    assert "full name" in reply.lower()

    # 3. Patient supplies their name -> confirmation prompt.
    reply = await _turn(monkeypatch, db_session, clinic, conversation, patient, "my name is ali")
    assert "confirm" in reply.lower()
    assert "Dental Cleaning" in reply

    # 4. Confirm -> appointment created and validated.
    reply = await _turn(monkeypatch, db_session, clinic, conversation, patient, "yes")
    assert "has been booked" in reply

    # Verify the appointment actually exists in the database.
    from app.database.models import Appointment

    appointments = (
        db_session.query(Appointment)
        .filter(Appointment.clinic_id == clinic.id, Appointment.patient_id == patient.id)
        .all()
    )
    assert len(appointments) == 1
    assert appointments[0].status == "scheduled"
    assert appointments[0].scheduled_at.date().isoformat() == monday
    assert appointments[0].service_label == "Dental Cleaning"
    assert patient.full_name == "Ali"

    # State is reset after a completed booking.
    state = conversation_service.conversation_state(conversation)
    assert state.get("intent") is None
    assert state.get("awaiting") is None