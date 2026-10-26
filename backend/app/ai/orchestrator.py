"""AI orchestrator (build plan 5.2 / 5.13).

Execution loop:
1. Load conversation + safety pre-check
2. Determine intent (structured output)
3. Route to the right flow (FAQ/RAG, booking, cancel, reschedule, handoff)
4. Execute backend tools (validated)
5. Ask the LLM to formulate/ground the response
6. Validate the response against DB truth
7. Save AI events + conversation state
"""
import logging
import re
import time

from sqlalchemy.orm import Session

from app.ai.client import generate_response
from app.ai.events import record_ai_event
from app.ai.intent import detect_intent
from app.ai.prompts import build_system_prompt, clinic_profile, grounded_answer_prompt
from app.ai.rag import retrieve
from app.ai.safety import (
    emergency_response,
    medical_advice_response,
    safety_precheck,
    wants_human_handoff,
)
from app.ai.state import (
    booking_summary,
    combine_datetime,
    default_state,
    is_affirmative,
    is_negative,
    merge_entities,
    parse_date_value,
    parse_time_value,
    resolve_index,
)
from app.ai.tools import (
    cancel_appointment as tool_cancel_appointment,
    check_availability as tool_check_availability,
    create_appointment as tool_create_appointment,
    create_lead as tool_create_lead,
    handoff_to_human as tool_handoff_to_human,
    reschedule_appointment as tool_reschedule_appointment,
)
from app.ai.validation import validate_response
from app.database.models import Clinic, Conversation, Patient
from app.services import (
    appointment_service,
    conversation_service,
    doctor_service,
    lead_service,
    service_service,
)

logger = logging.getLogger(__name__)

BOOKING_INTENTS = {"BOOK_APPOINTMENT", "PROVIDE_PATIENT_INFO"}


async def process_message(clinic_name: str, user_message: str) -> str:
    """Level-1 orchestrator (build plan 5.1). Used by /test-chat."""
    system_prompt = build_system_prompt(clinic_name)
    return await generate_response(system_prompt, user_message)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_state(conversation: Conversation) -> dict:
    raw = conversation.state or {}
    return {**default_state(), **raw}


def _match_label(label: str, choices: list, attr: str = "name"):
    if not label:
        return None
    needle = label.lower().strip()
    for choice in choices:
        target = (getattr(choice, attr) or "").lower()
        if needle in target or target in needle:
            return choice
    return None


def _resolve_service(db, clinic, state, services):
    if state.get("service_id"):
        service = service_service.get_service(db, clinic, state["service_id"])
        if service:
            return service, state
    if state.get("service_label"):
        service = _match_label(state["service_label"], services)
        if service:
            state["service_id"] = service.id
            state["service_label"] = service.name
            return service, state
    if len(services) == 1:
        service = services[0]
        state["service_id"] = service.id
        state["service_label"] = service.name
        return service, state
    return None, state


def _resolve_doctor(db, clinic, state, doctors):
    if state.get("doctor_id"):
        doctor = doctor_service.get_doctor(db, clinic, state["doctor_id"])
        if doctor:
            return doctor, state
    if state.get("doctor_label"):
        doctor = _match_label(state["doctor_label"], doctors)
        if doctor:
            state["doctor_id"] = doctor.id
            state["doctor_label"] = doctor.name
            return doctor, state
    if len(doctors) == 1:
        doctor = doctors[0]
        state["doctor_id"] = doctor.id
        state["doctor_label"] = doctor.name
        return doctor, state
    return None, state


def _ask_choose_service(services) -> str:
    options = "\n".join(f"{i+1}. {s.name}" for i, s in enumerate(services))
    return f"Which service would you like? Reply with the number or name:\n{options}"


def _ask_choose_doctor(doctors) -> str:
    options = "\n".join(f"{i+1}. Dr. {d.name}" for i, d in enumerate(doctors))
    return f"Which doctor would you prefer? Reply with the number, or 'earliest'.\n{options}"


def _ask_date() -> str:
    return "What date works for you? (For example: tomorrow, Saturday, or a specific date like 2026-10-05)"


def _format_times(slots) -> str:
    return ", ".join(
        s.strftime("%I:%M %p").lstrip("0") for s in slots[:5]
    )


def _ask_time(state: dict) -> str:
    slots = state.get("offered_slots", [])[:5]
    day = state.get("selected_date")
    text = f"Available times on {day}: {', '.join(f'{i+1}. {s.split()[-1]}' for i, s in enumerate(slots))}."
    return text + " Which time works for you?"


def _ask_name() -> str:
    return "May I have your full name for the appointment?"


def _ask_confirm(state: dict) -> str:
    return f"Please confirm your appointment: {booking_summary(state)}. Reply CONFIRM or type 'yes' to book it."


def _slot_time_from_offered(message: str, state: dict) -> str | None:
    idx = resolve_index(message)
    offered = state.get("offered_slots") or []
    if idx is not None and 1 <= idx <= len(offered):
        return offered[idx - 1].split(" ")[-1]
    return parse_time_value(message)
# --------------------------------------------------------------------------- #
# Flows
# --------------------------------------------------------------------------- #
def _choose_from_message(message, choices):
    idx = resolve_index(message)
    if idx is not None and 1 <= idx <= len(choices):
        return choices[idx - 1]
    candidate = _match_label(message, choices)
    return candidate


async def _handle_booking(db, clinic, conversation, message, intent, state, services, doctors, patient):
    # Service
    service, state = _resolve_service(db, clinic, state, services)
    if service is None:
        if not services:
            lead_service.create_lead(
                db,
                clinic,
                name=state.get("patient_name"),
                phone=patient.phone_number,
                service=state.get("service_label"),
                source=conversation.channel,
                notes="Service not resolvable — staff follow-up",
            )
            record_ai_event(
                db, clinic_id=clinic.id, conversation_id=conversation.id,
                event_type="tool_call", input_data={"tool": "create_lead"},
            )
            return (
                "I couldn't find that service in our online catalog. I've saved your request — "
                "a staff member will contact you to help book it."
            ), default_state()

        if state.get("awaiting") != "service" and not state.get("service_label"):
            state["awaiting"] = "service"
        return _ask_choose_service(services), state

    # Doctor (optional)
    doctor, state = _resolve_doctor(db, clinic, state, doctors)
    if doctor is None and len(doctors) > 1 and state.get("awaiting") not in (
        "date", "time", "name", "confirmation",
    ):
        state["awaiting"] = "doctor"
        return _ask_choose_doctor(doctors), state

    # Doctor selection answer
    if state.get("awaiting") == "doctor":
        chosen = None
        idx = resolve_index(message)
        if idx is not None and 1 <= idx <= len(doctors):
            chosen = doctors[idx - 1]
        elif "earliest" in message.lower() and doctors:
            chosen = doctors[0]
        else:
            candidate = _match_label(message, doctors)
            if candidate is not None:
                chosen = candidate
        if chosen is not None:
            state["doctor_id"] = chosen.id
            state["doctor_label"] = chosen.name
            state["awaiting"] = None
        else:
            return _ask_choose_doctor(doctors), state

    # Service selection answer
    if state.get("awaiting") == "service":
        chosen = _choose_from_message(message, services)
        if chosen is not None:
            state["service_id"] = chosen.id
            state["service_label"] = chosen.name
            state["awaiting"] = None
        else:
            return _ask_choose_service(services), state
# Availability question answered with a date
    if state.get("awaiting") == "availability_date":
        parsed = parse_date_value(message, None)
        if parsed:
            state["selected_date"] = parsed
            state["awaiting"] = None
        elif not state.get("selected_date"):
            return _ask_date(), state

    # Date — an explicit date/relative phrase in THIS message always wins over
    # any LLM guess; an already-vetted selected_date (previous turns) is kept.
    parsed = parse_date_value(message, None)
    if parsed:
        state["selected_date"] = parsed
    elif not state.get("selected_date"):
        state["awaiting"] = "date"
        return _ask_date(), state

    # Time
    on_date = state["selected_date"]
    if not state.get("selected_time"):
        if not state.get("offered_slots") or state.get("awaiting") != "time":
            from datetime import date as dt_date

            slots = tool_check_availability(
                db, clinic, on_date=dt_date.fromisoformat(on_date),
                doctor_id=state.get("doctor_id"), service_id=state.get("service_id"),
            )
            if not slots:
                # Reset the bad date so the next message starts a fresh date
                # prompt instead of looping on the same failed slot lookup.
                state["selected_date"] = None
                state["offered_slots"] = []
                state["awaiting"] = "date"
                return (
                    f"Sorry, the clinic has no available slots on {on_date}. "
                    "What other date would you like to try?"
                ), state
            state["offered_slots"] = [s.strftime("%Y-%m-%d %H:%M") for s in slots]
            state["awaiting"] = "time"
            return _ask_time(state), state

        # The patient has just answered the time question ("1", "3pm", ...).
        chosen = _slot_time_from_offered(message, state)
        if not chosen:
            return _ask_time(state), state
        state["selected_time"] = chosen
        state["awaiting"] = None

    # Name answer (the patient usually just types their name, or "My name is X").
    # The LLM *may* also extract patient_name as an entity (already merged above) —
    # in that case we skip this block; otherwise the raw reply is parsed so we
    # never loop on the name prompt.
    if state.get("awaiting") == "name" and not state.get("patient_name"):
        name = (message or "").strip().strip(".,!?")
        intro = re.match(r"^(?:my name is|my name's|i am|i'm)\s+(.+)$", name.lower())
        candidate = re.sub(r"\s+", " ", intro.group(1) if intro else name).strip(".,!?")
        if (
            candidate
            and not is_affirmative(candidate)
            and not is_negative(candidate)
            and not candidate.isdigit()
            and len(candidate) <= 60
            and "?" not in candidate
            and "\n" not in candidate
            and "," not in candidate
        ):
            state["patient_name"] = candidate.title() if len(candidate.split()) <= 3 else candidate
            state["awaiting"] = None
        else:
            return _ask_name(), state

    # Name
    if not state.get("patient_name"):
        if patient.full_name:
            state["patient_name"] = patient.full_name
        else:
            state["awaiting"] = "name"
            return _ask_name(), state

    # Confirmation
    if state.get("awaiting") == "confirmation":
        if is_affirmative(message):
            return await _finalize_booking(db, clinic, conversation, state, patient)
        if is_negative(message):
            state["selected_time"] = None
            state["offered_slots"] = []
            state["awaiting"] = "date"
            return "No problem. What date works for you instead?", state
        return _ask_confirm(state), state

    state["awaiting"] = "confirmation"
    return _ask_confirm(state), state


async def _finalize_booking(db, clinic, conversation, state, patient):
    scheduled_at = combine_datetime(state["selected_date"], state["selected_time"])
    if scheduled_at is None:
        state["selected_time"] = None
        state["awaiting"] = "time"
        return "I couldn't read that time. Could you repeat it?", state
    try:
        appointment = tool_create_appointment(
            db,
            clinic,
            patient_id=patient.id,
            service_id=state.get("service_id"),
            doctor_id=state.get("doctor_id"),
            service_label=state.get("service_label"),
            scheduled_at=scheduled_at,
            source=conversation.channel,
        )
    except ValueError as exc:
        state["selected_time"] = None
        state["offered_slots"] = []
        state["awaiting"] = "time"
        return (f"Sorry, that slot just became unavailable ({exc}). "
                "Let me show you other options."), state

    record_ai_event(
        db, clinic_id=clinic.id, conversation_id=conversation.id,
        event_type="tool_call",
        input_data={"tool": "create_appointment", "appointment_id": appointment.id},
        output_data={"scheduled_at": scheduled_at.isoformat(), "status": appointment.status},
    )
    if patient.full_name != state.get("patient_name"):
        patient.full_name = state.get("patient_name") or ""
        db.flush()

    new_state = default_state()
    when = scheduled_at.strftime("%A, %d %B %Y at %H:%M")
    label = state.get("service_label") or "consultation"
    return (
        f"Your appointment has been booked for {label} on {when}. "
        f"Thank you, {state.get('patient_name')}! We'll send you a reminder before your appointment."
    ), new_state
async def _handle_availability(db, clinic, state, message):
    if not state.get("selected_date"):
        parsed = parse_date_value(message, state.get("selected_date"))
        if not parsed:
            state["awaiting"] = "availability_date"
            return _ask_date(), state
        state["selected_date"] = parsed
        state["awaiting"] = None

    from datetime import date as dt_date

    slots = tool_check_availability(
        db, clinic, on_date=dt_date.fromisoformat(state["selected_date"]),
        doctor_id=state.get("doctor_id"), service_id=state.get("service_id"),
    )
    if not slots:
        chosen = state["selected_date"]
        state["selected_date"] = None
        state["offered_slots"] = []
        state["awaiting"] = "availability_date"
        return (f"There are no available slots on {chosen}. "
                "Which date would you like to check instead?"), state
    formatted = _format_times(slots)
    return (
        f"Available times on {state['selected_date']}: {formatted}. "
        "Would you like to book one of these times?"
    ), state


async def _handle_cancel(db, clinic, patient, message, state):
    if state.get("awaiting") == "cancel_confirm":
        if is_affirmative(message):
            appointment = tool_cancel_appointment(db, clinic, state.get("cancel_appointment_id"))
            if appointment is None:
                return "I couldn't find that appointment. It may have already been removed.", default_state()
            record_ai_event(
                db, clinic_id=clinic.id, event_type="tool_call",
                input_data={"tool": "cancel_appointment", "appointment_id": appointment.id},
            )
            return "Your appointment has been cancelled.", default_state()
        return "Okay, I haven't cancelled anything.", default_state()

    upcoming = appointment_service.upcoming_appointments(db, clinic, patient.id)
    if not upcoming:
        return "You don't have any upcoming appointments at the moment.", state
    appointment = upcoming[0]
    state["cancel_appointment_id"] = appointment.id
    state["awaiting"] = "cancel_confirm"
    label = appointment.service_label or "consultation"
    when = appointment.scheduled_at.strftime("%A, %d %B %Y at %H:%M") if appointment.scheduled_at else "TBD"
    return f"You have an upcoming {label} appointment on {when}. Reply CONFIRM to cancel it.", state


async def _handle_reschedule(db, clinic, patient, message, state):
    target_id = state.get("reschedule_appointment_id")
    appointment = None
    if target_id is not None:
        appointment = appointment_service.get_appointment(db, clinic, target_id)
    if appointment is None:
        upcoming = appointment_service.upcoming_appointments(db, clinic, patient.id)
        if not upcoming:
            return "You don't have any upcoming appointments to reschedule.", state
        appointment = upcoming[0]
        state["reschedule_appointment_id"] = appointment.id
        state["awaiting"] = "reschedule_date"
        when = appointment.scheduled_at.strftime("%A, %d %B %Y at %H:%M") if appointment.scheduled_at else "TBD"
        label = appointment.service_label or "consultation"
        return f"Sure. Your {label} appointment is on {when}. What date would you prefer?", state

    if state.get("awaiting") == "reschedule_date":
        parsed = parse_date_value(message, None)
        if not parsed:
            return "What date would you prefer? (For example: tomorrow, Saturday, or a specific date)", state
        state["selected_date"] = parsed
        from datetime import date as dt_date

        slots = tool_check_availability(
            db, clinic, on_date=dt_date.fromisoformat(parsed),
            doctor_id=appointment.doctor_id, service_id=appointment.service_id,
        )
        if not slots:
            state["selected_date"] = None
            state["awaiting"] = "reschedule_date"
            return f"There are no available slots on {parsed}. What other date would you prefer?", state
        state["offered_slots"] = [s.strftime("%Y-%m-%d %H:%M") for s in slots]
        state["awaiting"] = "reschedule_time"
        return _ask_time(state), state

    if state.get("awaiting") == "reschedule_time":
        chosen = _slot_time_from_offered(message, state)
        if not chosen:
            return "Which time would you like?", state
        state["selected_time"] = chosen
        scheduled_at = combine_datetime(state["selected_date"], chosen)
        try:
            updated = tool_reschedule_appointment(db, clinic, appointment.id, scheduled_at)
        except ValueError as exc:
            return f"Sorry, that time is not available ({exc}).", state
        if updated is None:
            return "I couldn't find that appointment anymore.", default_state()
        record_ai_event(
            db, clinic_id=clinic.id, event_type="tool_call",
            input_data={"tool": "reschedule_appointment", "appointment_id": appointment.id},
            output_data={"scheduled_at": scheduled_at.isoformat()},
        )
        when = scheduled_at.strftime("%A, %d %B %Y at %H:%M")
        return f"Your appointment has been rescheduled to {when}.", default_state()

    return "Let's reschedule. What date would you prefer?", state


async def _handle_faq(db, clinic, message):
    try:
        results = await retrieve(db, clinic.id, message, k=4)
    except Exception as exc:  # no embedding provider configured, etc.
        record_ai_event(
            db, clinic_id=clinic.id, event_type="error",
            input_data={"step": "rag_retrieval", "message": message},
            output_data={"error": str(exc)},
        )
        results = []
    if results:
        snippets = [r["content"] for r in results]
        system = grounded_answer_prompt(clinic.name, snippets)
        return await generate_response(system, message)
    system = f"{build_system_prompt(clinic.name)}\n\n{clinic_profile(clinic)}"
    return await generate_response(system, message)
# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #
async def handle_message(
    db: Session,
    *,
    clinic: Clinic,
    patient: Patient,
    conversation: Conversation,
    user_message: str,
) -> str:
    """Full receptionist loop. The caller persists messages and commits."""
    start = time.monotonic()
    services = service_service.list_services(db, clinic)
    doctors = doctor_service.list_doctors(db, clinic)
    state = _load_state(conversation)

    # 1. Safety pre-check (build plan 5.8)
    safety = safety_precheck(user_message, state.get("intent"))
    if safety.level != "safe":
        record_ai_event(
            db, clinic_id=clinic.id, conversation_id=conversation.id,
            event_type="safety",
            input_data={"message": user_message},
            output_data={"level": safety.level, "reason": safety.reason},
        )
        if safety.level == "emergency":
            tool_handoff_to_human(db, clinic, conversation, reason=f"emergency:{safety.reason}")
        return emergency_response(clinic) if safety.level == "emergency" else medical_advice_response(clinic)

    # 2. Human-active guard: once staff takes over, the AI stops (5.9)
    if conversation.status == "human_active":
        return "A staff member is now assisting you, so I've paused my responses."

    # 3. Intent detection (5.2 / 5.4)
    intent_result = await detect_intent(
        clinic,
        user_message,
        services=[s.name for s in services],
        doctors=[d.name for d in doctors],
        db=db,
        conversation_id=conversation.id,
    )
    intent = intent_result.intent
    state = merge_entities(state, intent_result.entities)
    state["intent"] = intent
    state["confidence"] = intent_result.confidence

    reply: str
    new_state: dict = state

    if intent == "HUMAN_HANDOFF" or wants_human_handoff(user_message):
        tool_handoff_to_human(db, clinic, conversation, reason=user_message)
        record_ai_event(
            db, clinic_id=clinic.id, conversation_id=conversation.id,
            event_type="handoff", input_data={"reason": user_message},
        )
        reply = (
            "I've connected you with our staff. A member of the clinic team will reply shortly. "
            "You can also call us directly if it's urgent."
        )
        new_state = default_state()
    elif intent == "EMERGENCY":
        tool_handoff_to_human(db, clinic, conversation, reason="emergency (LLM intent)")
        reply = emergency_response(clinic)
        new_state = default_state()
    elif intent == "CANCEL_APPOINTMENT" or state.get("awaiting") == "cancel_confirm":
        reply, new_state = await _handle_cancel(db, clinic, patient, user_message, state)
    elif intent == "RESCHEDULE_APPOINTMENT" or (state.get("awaiting") or "").startswith("reschedule"):
        reply, new_state = await _handle_reschedule(db, clinic, patient, user_message, state)
    elif intent == "CHECK_AVAILABILITY" and not (state.get("awaiting") or "").startswith("avail"):
        reply, new_state = await _handle_availability(db, clinic, state, user_message)
    elif intent in BOOKING_INTENTS or (state.get("awaiting") and intent != "FAQ"):
        reply, new_state = await _handle_booking(
            db, clinic, conversation, user_message, intent, state, services, doctors, patient
        )
    elif intent == "FAQ":
        reply = await _handle_faq(db, clinic, user_message)
    else:  # UNKNOWN
        reply = await generate_response(
            f"{build_system_prompt(clinic.name)}\n\n{clinic_profile(clinic)}", user_message
        )

    # 4. Response validation against DB truth (5.11)
    validated = await validate_response(
        db, clinic, patient, reply, intent=intent, state=new_state
    )
    if validated != reply:
        record_ai_event(
            db, clinic_id=clinic.id, conversation_id=conversation.id,
            event_type="error", input_data={"step": "response_validation"},
            output_data={"original": reply[:200], "fallback": validated},
        )

    # 5. Persist state + patient name
    conversation_service.save_state(db, conversation, new_state)
    if new_state.get("patient_name") and not patient.full_name:
        patient.full_name = new_state["patient_name"]
        db.flush()

    record_ai_event(
        db, clinic_id=clinic.id, conversation_id=conversation.id,
        event_type="llm_response",
        input_data={"message": user_message},
        output_data={"intent": intent, "reply": validated[:300]},
        latency_ms=int((time.monotonic() - start) * 1000),
    )
    return validated