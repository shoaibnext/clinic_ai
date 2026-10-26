"""Response validation (build plan 5.11).

Never blindly send the LLM's output. If it claims a booking/cancellation happened
but the backend never did it, replace the reply with an honest fallback.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.database.models import Appointment, Clinic, Patient

FALLBACK_BOOKING = (
    "I wasn't able to confirm that appointment yet. "
    "Let me double-check and get back to you — or a staff member will follow up shortly."
)
FALLBACK_CANCEL = (
    "I wasn't able to cancel that appointment yet. "
    "A staff member will follow up with you shortly."
)


def _appointment_created_recently(
    db: Session,
    clinic: Clinic,
    patient: Patient,
    selected_date: str | None,
    selected_time: str | None,
    window_minutes: int = 5,
) -> bool:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    if selected_date and selected_time:
        try:
            starts = datetime.fromisoformat(f"{selected_date}T{selected_time}").replace(tzinfo=UTC)
        except ValueError:
            starts = None
    else:
        starts = None
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.clinic_id == clinic.id,
            Appointment.patient_id == patient.id,
            Appointment.status == "scheduled",
            Appointment.created_at >= cutoff,
        )
        .all()
    )
    if not appointments:
        return False
    if starts is None:
        return True
    return any(
        a.scheduled_at is not None
        and abs(a.scheduled_at.replace(tzinfo=UTC) - starts) <= timedelta(minutes=10)
        for a in appointments
    )


def _appointment_cancelled_recently(
    db: Session,
    clinic: Clinic,
    patient: Patient,
    window_minutes: int = 5,
) -> bool:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    return (
        db.query(Appointment)
        .filter(
            Appointment.clinic_id == clinic.id,
            Appointment.patient_id == patient.id,
            Appointment.status == "cancelled",
            Appointment.created_at >= cutoff,
        )
        .count()
        > 0
    )


async def validate_response(
    db: Session,
    clinic: Clinic,
    patient: Patient,
    reply: str,
    *,
    intent: str | None,
    state: dict,
) -> str:
    lowered = reply.lower()
    if intent == "BOOK_APPOINTMENT" and (
        "confirmed" in lowered or "has been booked" in lowered or "appointment is booked" in lowered
    ):
        if not _appointment_created_recently(
            db, clinic, patient, state.get("selected_date"), state.get("selected_time")
        ):
            return FALLBACK_BOOKING
    elif (
        intent == "CANCEL_APPOINTMENT"
        and "cancel" in lowered
        and state.get("awaiting") != "cancel_confirm"
    ):
        # The cancellation confirmation PROMPT ("...Reply CONFIRM to cancel it.")
        # is produced while waiting for the patient's confirmation (awaiting ==
        # "cancel_confirm"). It is not a claim that a cancellation happened, so
        # it must pass through unchanged; only replies that claim the
        # cancellation was executed are checked against the database.
        if not _appointment_cancelled_recently(db, clinic, patient):
            return FALLBACK_CANCEL
    return reply