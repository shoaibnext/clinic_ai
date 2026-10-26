"""Conversation state (build plan 5.3). Structured state persisted on the Conversation row."""

import re
from datetime import date, datetime, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

AFFIRMATIVE = {"yes", "yeah", "yep", "y", "sure", "ok", "okay", "confirm", "confirmed", "correct", "right", "book", "go ahead", "do it", "agree"}
NEGATIVE = {"no", "nope", "nah", "not", "cancel", "nevermind", "never mind", "wrong", "no thanks", "n"}


def default_state() -> dict:
    return {
        "intent": None,
        "awaiting": None,
        "service_id": None,
        "service_label": None,
        "doctor_id": None,
        "doctor_label": None,
        "selected_date": None,
        "selected_time": None,
        "patient_name": None,
        "offered_slots": [],
        "cancel_appointment_id": None,
        "reschedule_appointment_id": None,
    }


def _sane_date(value: date) -> bool:
    """A date is sane when it is roughly now (or yesterday) .. up to 5 years ahead.

    The forward bound is intentionally generous (clinics can take advance
    bookings); the main job is rejecting PAST and obviously bogus dates that the
    LLM can hallucinate for relative phrases ('tomorrow' -> 2025-05-23).
    """
    today = date.today()
    return today - timedelta(days=1) <= value <= today + timedelta(days=1826)


def merge_entities(state: dict, entities: dict) -> dict:
    """Copy non-empty extracted entities into the working state.

    Dates are vetted before being accepted: only ISO dates inside a sane window
    are stored. Relative dates and bogus LLM guesses ("tomorrow" -> 2025-05-23)
    are dropped here; the booking flow then re-parses relative phrases
    deterministically from the raw message text.
    """
    if entities.get("service"):
        state["service_label"] = entities["service"]
    if entities.get("doctor"):
        state["doctor_label"] = entities["doctor"]
    if entities.get("date"):
        candidate = str(entities["date"]).strip()
        try:
            parsed = date.fromisoformat(candidate)
        except ValueError:
            parsed = None
        if parsed is not None and _sane_date(parsed):
            state["selected_date"] = candidate
    if entities.get("time"):
        state["selected_time"] = entities["time"]
    if entities.get("patient_name"):
        state["patient_name"] = entities["patient_name"]
    return state


def is_booking_flow_active(state: dict) -> bool:
    return bool(state.get("intent")) or bool(state.get("awaiting"))


def missing_booking_fields(state: dict) -> list[str]:
    missing = []
    if not state.get("service_id") and not state.get("service_label"):
        missing.append("service")
    if not state.get("selected_date"):
        missing.append("date")
    if not state.get("selected_time"):
        missing.append("time")
    if not state.get("patient_name"):
        missing.append("name")
    return missing


def booking_summary(state: dict) -> str:
    label = state.get("service_label") or f"service #{state.get('service_id')}"
    parts = [label]
    if state.get("doctor_label"):
        parts.append(f"with {state['doctor_label']}")
    parts.append(f"on {state['selected_date']} at {state['selected_time']}")
    return " ".join(parts)


def is_affirmative(text: str) -> bool:
    tokens = {t.strip(".,!?") for t in text.lower().split()}
    return bool(tokens & AFFIRMATIVE)


def is_negative(text: str) -> bool:
    tokens = {t.strip(".,!?") for t in text.lower().split()}
    return bool(tokens & NEGATIVE)


def resolve_index(text: str) -> int | None:
    """Return 1-based index if the message is a bare number / ordinal like '2' or 'first'."""
    text = text.strip().lower()
    match = re.fullmatch(r"(\d+)", text)
    if match:
        return int(match.group(1))
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1}
    return ordinals.get(text)


def parse_date_value(text: str, entity_date: str | None = None) -> str | None:
    """Resolve a date to YYYY-MM-DD from user text or a validated entity.

    Priority:
    1. Relative/explicit dates in the message text itself ('today', 'tomorrow',
       'day after tomorrow', weekday names, ISO 'YYYY-MM-DD', 'DD/MM/YYYY').
       These are resolved deterministically against the real current date, so
       the caller never depends on an LLM doing calendar arithmetic.
    2. An extracted `entity_date` — but ONLY when it is a valid ISO date inside
       a sane window. LLM-hallucinated absolute dates for relative phrases are
       rejected here so they can never reach a booking/slot check.
    """
    lower = text.lower().strip()
    today = date.today()
    if "day after tomorrow" in lower:
        return (today + timedelta(days=2)).isoformat()
    if "tomorrow" in lower:
        return (today + timedelta(days=1)).isoformat()
    if "today" in lower:
        return today.isoformat()
    for name, offset in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", lower):
            delta = (offset - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return (today + timedelta(days=delta)).isoformat()

    match = re.search(r"\d{4}-\d{2}-\d{2}", lower)
    if match:
        try:
            parsed = date.fromisoformat(match.group(0))
            if _sane_date(parsed):
                return parsed.isoformat()
        except ValueError:
            pass

    match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", lower)
    if match:
        dd, mm, yy = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if mm > 12 and dd <= 12:  # DD/MM/YYYY by default; swap clearly-MM/DD inputs
            dd, mm = mm, dd
        try:
            parsed = date(yy, mm, dd)
            if _sane_date(parsed):
                return parsed.isoformat()
        except ValueError:
            pass

    if entity_date:
        candidate = entity_date.strip()
        try:
            parsed = date.fromisoformat(candidate)
            if _sane_date(parsed):
                return parsed.isoformat()
        except ValueError:
            pass
    return None


def parse_time_value(text: str, entity_time: str | None = None) -> str | None:
    """Resolve a time to 24h 'HH:MM' from message text or extracted entity."""
    if entity_time:
        candidate = entity_time.strip()
        if re.fullmatch(r"\d{1,2}:\d{2}", candidate):
            hour, minute = candidate.split(":")
            return f"{int(hour):02d}:{int(minute):02d}"
    lower = text.lower()
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def combine_datetime(date_str: str, time_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError:
        return None