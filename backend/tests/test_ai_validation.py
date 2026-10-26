from datetime import datetime, timedelta

import pytest
from app.ai.validation import validate_response
from app.ai.state import default_state


def _make_patient(db_session, clinic):
    from app.services.patient_service import create_patient

    return create_patient(db_session, clinic, phone_number="+15550107777")


@pytest.mark.asyncio
async def test_keep_reply_when_no_claim(db_session, clinic, patient):
    state = default_state()
    reply = await validate_response(
        db_session, clinic, patient, "Which service would you like?", intent="FAQ", state=state
    )
    assert reply == "Which service would you like?"


@pytest.mark.asyncio
async def test_booking_claim_without_appointment_is_guarded(db_session, clinic, patient):
    state = default_state()
    reply = await validate_response(
        db_session,
        clinic,
        patient,
        "Your appointment has been booked. Confirmed!",
        intent="BOOK_APPOINTMENT",
        state=state,
    )
    assert "wasn't able to confirm" in reply


@pytest.mark.asyncio
async def test_booking_claim_with_recent_appointment_passes(db_session, clinic, patient):
    from app.services.appointment_service import create_appointment

    scheduled_at = datetime.now() + timedelta(days=3)
    create_appointment(
        db_session,
        clinic,
        patient_id=patient.id,
        service_label="Checkup",
        scheduled_at=scheduled_at,
    )

    state = default_state()
    state["selected_date"] = scheduled_at.date().isoformat()
    state["selected_time"] = scheduled_at.strftime("%H:%M")
    reply = await validate_response(
        db_session,
        clinic,
        patient,
        "Your appointment has been booked. Confirmed!",
        intent="BOOK_APPOINTMENT",
        state=state,
    )
    assert reply == "Your appointment has been booked. Confirmed!"


@pytest.mark.asyncio
async def test_cancel_claim_without_cancellation_is_guarded(db_session, clinic, patient):
    state = default_state()
    reply = await validate_response(
        db_session,
        clinic,
        patient,
        "Your appointment has been cancelled.",
        intent="CANCEL_APPOINTMENT",
        state=state,
    )
    assert "wasn't able to cancel" in reply


@pytest.mark.asyncio
async def test_cancel_claim_with_recent_cancellation_passes(db_session, clinic, patient):
    from app.database.models import Appointment
    from app.services.appointment_service import create_appointment

    appointment = create_appointment(
        db_session,
        clinic,
        patient_id=patient.id,
        service_label="Checkup",
        scheduled_at=datetime.now() + timedelta(days=3),
    )
    appointment.status = "cancelled"
    db_session.commit()

    state = default_state()
    reply = await validate_response(
        db_session,
        clinic,
        patient,
        "Your appointment has been cancelled.",
        intent="CANCEL_APPOINTMENT",
        state=state,
    )
    assert reply == "Your appointment has been cancelled."
@pytest.mark.asyncio
async def test_cancel_confirmation_prompt_is_not_replaced(db_session, clinic, patient):
    """Regression: the cancellation confirmation PROMPT must survive validation.

    When the state machine is waiting for the patient's confirmation
    (awaiting == "cancel_confirm"), the assistant's reply is the prompt
    "Reply CONFIRM to cancel it." — a proposal, not a claim that a cancellation
    happened. It must NOT be replaced by FALLBACK_CANCEL even though
    intent == CANCEL_APPOINTMENT and the prompt contains the word "cancel".
    """
    state = default_state()
    state["awaiting"] = "cancel_confirm"
    prompt = (
        "You have an upcoming Checkup appointment on Monday, 05 October 2026 at 09:00. "
        "Reply CONFIRM to cancel it."
    )
    reply = await validate_response(
        db_session, clinic, patient, prompt, intent="CANCEL_APPOINTMENT", state=state
    )
    assert reply == prompt
    assert "wasn't able to cancel" not in reply


@pytest.mark.asyncio
async def test_cancel_claim_after_confirmation_is_still_checked(db_session, clinic, patient):
    """The guard must still fire after the confirmation state is gone.

    Once the patient confirmed and the flow left the cancel_confirm state, a
    cancellation claim with no matching DB change must still be replaced.
    """
    state = default_state()  # awaiting is None (post-confirmation)
    reply = await validate_response(
        db_session,
        clinic,
        patient,
        "Your appointment has been cancelled.",
        intent="CANCEL_APPOINTMENT",
        state=state,
    )
    assert reply == (
        "I wasn't able to cancel that appointment yet. "
        "A staff member will follow up with you shortly."
    )