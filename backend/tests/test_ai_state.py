from datetime import date, datetime, timedelta

from app.ai.state import (
    booking_summary,
    combine_datetime,
    default_state,
    is_affirmative,
    is_negative,
    merge_entities,
    missing_booking_fields,
    parse_date_value,
    parse_time_value,
    resolve_index,
)


def test_default_state_is_complete():
    state = default_state()
    for key in (
        "intent", "awaiting", "service_id", "service_label", "doctor_id",
        "doctor_label", "selected_date", "selected_time", "patient_name",
        "offered_slots", "cancel_appointment_id", "reschedule_appointment_id",
    ):
        assert key in state


def test_parse_date_iso():
    # Use a future date — past dates are intentionally rejected by the parser.
    future = (date.today() + timedelta(days=30)).isoformat()
    assert parse_date_value(future) == future


def test_parse_date_today_and_tomorrow():
    today = date.today()
    assert parse_date_value("today") == today.isoformat()
    assert parse_date_value("tomorrow") == (today + timedelta(days=1)).isoformat()


def test_parse_date_weekday():
    monday = parse_date_value("monday")
    parsed = date.fromisoformat(monday)
    assert parsed.weekday() == 0
    assert parsed >= date.today()


def test_parse_date_entity_overrides():
    assert parse_date_value("whatever", entity_date="2030-01-15") == "2030-01-15"


def test_parse_date_invalid():
    # A bare weekday phrase still resolves to the next occurrence.
    parsed = parse_date_value("next tuesday")
    assert parsed is not None
    assert date.fromisoformat(parsed).weekday() == 1
    assert parse_date_value("") is None
    assert parse_date_value("sometime soon") is None


def test_parse_date_ddmmyyyy():
    # Dates are computed relative to the real current date (only sane windows pass).
    future = (date.today() + timedelta(days=40)).isoformat()
    yy, mm, dd = future.split("-")
    assert parse_date_value(f"{dd}/{mm}/{yy}") == future

    # Clearly-MM/DD written dates (month component > 12) are swapped.
    swapped = (date.today() + timedelta(days=400)).isoformat()
    syy, smm, sdd = swapped.split("-")
    assert parse_date_value(f"{smm}/{sdd}/{syy}") == swapped


def test_parse_date_rejects_past_entity():
    # The exact bug seen in production: LLM guessed 2025-05-23 for "tomorrow".
    today = date.today()
    past = (today - timedelta(days=400)).isoformat()
    assert parse_date_value("tomorrow", entity_date=past) == (
        today + timedelta(days=1)
    ).isoformat()
    assert parse_date_value("something", entity_date=past) is None


def test_merge_entities_rejects_past_date():
    state = default_state()
    merge_entities(state, {"date": "2025-05-23"})
    assert state["selected_date"] is None


def test_merge_entities_keeps_sane_future_date():
    state = default_state()
    future = (date.today() + timedelta(days=30)).isoformat()
    merge_entities(state, {"date": future})
    assert state["selected_date"] == future


def test_parse_time_24h():
    assert parse_time_value("15:30") == "15:30"
    assert parse_time_value("3pm") == "15:00"
    assert parse_time_value("9am") == "09:00"
    assert parse_time_value("12:00 pm") == "12:00"
    assert parse_time_value("12am") == "00:00"


def test_parse_time_invalid():
    assert parse_time_value("26:00") is None
    assert parse_time_value("no time") is None


def test_affirmative_and_negative():
    assert is_affirmative("yes please")
    assert is_affirmative("CONFIRM")
    assert not is_affirmative("no")
    assert is_negative("nope")
    assert is_negative("No, thanks")
    assert not is_negative("yes")


def test_resolve_index():
    assert resolve_index("2") == 2
    assert resolve_index("first") == 1
    assert resolve_index("last") == -1
    assert resolve_index("2pm") is None


def test_merge_entities():
    state = default_state()
    future = (date.today() + timedelta(days=30)).isoformat()
    merge_entities(
        state,
        {
            "service": "Dental Cleaning",
            "doctor": "Dr. Khan",
            "date": future,
            "time": "15:00",
            "patient_name": "Ali",
        },
    )
    assert state["service_label"] == "Dental Cleaning"
    assert state["doctor_label"] == "Dr. Khan"
    assert state["selected_date"] == future
    assert state["selected_time"] == "15:00"
    assert state["patient_name"] == "Ali"


def test_missing_booking_fields():
    assert missing_booking_fields(default_state()) == ["service", "date", "time", "name"]
    state = default_state()
    state.update(service_label="X", selected_date="2026-10-05", selected_time="10:00", patient_name="Ali")
    assert missing_booking_fields(state) == []


def test_combine_datetime():
    assert combine_datetime("2026-10-05", "15:00") == datetime(2026, 10, 5, 15, 0)
    assert combine_datetime("not-a-date", "15:00") is None


def test_booking_summary():
    state = default_state()
    state.update(
        service_label="Dental Cleaning",
        doctor_label="Dr. Khan",
        selected_date="2026-10-05",
        selected_time="15:00",
    )
    summary = booking_summary(state)
    assert "Dental Cleaning" in summary
    assert "Dr. Khan" in summary
    assert "2026-10-05" in summary
    assert "15:00" in summary