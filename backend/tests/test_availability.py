from datetime import date, timedelta


def _next_weekday(weekday: int) -> date:
    today = date.today()
    delta = (weekday - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _create_availability(client, clinic_headers, doctor, service, **extra):
    payload = {
        "doctor_id": doctor.id,
        "service_id": service.id,
        "weekday": 0,
        "start_time": "09:00",
        "end_time": "17:00",
        "is_recurring": True,
    }
    payload.update(extra)
    return client.post("/availability", headers=clinic_headers, json=payload)


def test_create_recurring_availability(client, clinic_headers, doctor, service):
    res = _create_availability(client, clinic_headers, doctor, service)
    assert res.status_code == 201
    data = res.json()
    assert data["weekday"] == 0
    assert data["is_recurring"] is True
    assert data["status"] == "available"


def test_create_availability_requires_weekday_or_date(client, clinic_headers, doctor, service):
    res = client.post(
        "/availability",
        headers=clinic_headers,
        json={"doctor_id": doctor.id, "start_time": "09:00", "end_time": "17:00"},
    )
    assert res.status_code == 409


def test_create_availability_unknown_doctor(client, clinic_headers, service):
    res = client.post(
        "/availability",
        headers=clinic_headers,
        json={
            "doctor_id": 99999,
            "service_id": service.id,
            "weekday": 0,
            "start_time": "09:00",
            "end_time": "17:00",
        },
    )
    assert res.status_code == 409
    assert "Doctor not found" in res.json()["detail"]


def test_list_availability(client, clinic_headers, doctor, service):
    _create_availability(client, clinic_headers, doctor, service)
    res = client.get("/availability", headers=clinic_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_free_slots_recurring_monday(client, clinic_headers, doctor, service):
    _create_availability(client, clinic_headers, doctor, service)
    monday = _next_weekday(0)
    res = client.get(
        "/availability/slots",
        headers=clinic_headers,
        params={
            "on_date": monday.isoformat(),
            "doctor_id": doctor.id,
            "service_id": service.id,
        },
    )
    assert res.status_code == 200
    slots = res.json()
    assert slots, "expected at least one free slot on a Monday"
    for slot in slots:
        assert slot.startswith(monday.isoformat())
    # Slots are 30-min apart starting at 09:00 and must be unique/sorted.
    assert len(slots) == len(set(slots))
    assert slots == sorted(slots)


def test_free_slots_empty_on_wrong_day(client, clinic_headers, doctor, service):
    _create_availability(client, clinic_headers, doctor, service)
    # A Tuesday has no recurring Monday window.
    tuesday = _next_weekday(1)
    res = client.get(
        "/availability/slots",
        headers=clinic_headers,
        params={"on_date": tuesday.isoformat()},
    )
    assert res.status_code == 200
    assert res.json() == []


def test_free_slots_respects_unavailable_window(client, db_session, clinic, doctor, service):
    from app.database.models import Availability
    from app.services import availability_service

    window = availability_service.create_availability(
        db_session,
        clinic,
        doctor_id=doctor.id,
        service_id=service.id,
        weekday=0,
        start_time=__import__("datetime").time(9, 0),
        end_time=__import__("datetime").time(17, 0),
        is_recurring=True,
    )
    window.status = "unavailable"
    db_session.commit()

    monday = _next_weekday(0)
    assert availability_service.free_slots(db_session, clinic, target_date=monday) == []