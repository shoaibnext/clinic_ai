from datetime import datetime, timedelta


def _future_datetime(days: int = 30, hour: int = 10, minute: int = 0) -> str:
    dt = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days)
    return dt.isoformat()


def _create_appointment(client, clinic_headers, patient, **extra):
    payload = {
        "patient_id": patient.id,
        "service_label": "Dental Cleaning",
        "scheduled_at": _future_datetime(),
    }
    payload.update(extra)
    return client.post("/appointments", headers=clinic_headers, json=payload)


def test_create_appointment(client, clinic_headers, patient):
    res = _create_appointment(client, clinic_headers, patient)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "scheduled"
    assert data["patient_id"] == patient.id
    assert data["service_label"] == "Dental Cleaning"
    assert data["source"] == "whatsapp"


def test_create_appointment_requires_auth(client, patient):
    res = _create_appointment(client, {}, patient)
    assert res.status_code == 401


def test_create_appointment_in_past_conflict(client, clinic_headers, patient):
    past = (datetime.now() - timedelta(days=1)).isoformat()
    res = _create_appointment(client, clinic_headers, patient, scheduled_at=past)
    assert res.status_code == 409
    assert "future" in res.json()["detail"]


def test_create_appointment_unknown_patient(client, clinic_headers):
    res = _create_appointment(client, clinic_headers, type("P", (), {"id": 999999}))
    assert res.status_code == 409
    assert "Patient not found" in res.json()["detail"]


def test_create_appointment_same_slot_conflict(client, clinic_headers, patient):
    when = _future_datetime()
    assert _create_appointment(client, clinic_headers, patient, scheduled_at=when).status_code == 201
    res = _create_appointment(client, clinic_headers, patient, scheduled_at=when, service_label="Second")
    assert res.status_code == 409
    assert "available" in res.json()["detail"]


def test_list_appointments_and_filters(client, clinic_headers, patient):
    _create_appointment(client, clinic_headers, patient)
    assert len(client.get("/appointments", headers=clinic_headers).json()) == 1
    listed = client.get(
        "/appointments", headers=clinic_headers,
        params={"patient_id": patient.id, "status": "scheduled"},
    ).json()
    assert len(listed) == 1
    assert (
        client.get("/appointments", headers=clinic_headers, params={"status": "cancelled"}).json()
        == []
    )


def test_get_single_appointment(client, clinic_headers, patient):
    created = _create_appointment(client, clinic_headers, patient).json()
    res = client.get(f"/appointments/{created['id']}", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_appointment_not_found(client, clinic_headers):
    assert client.get("/appointments/99999", headers=clinic_headers).status_code == 404


def test_patch_appointment_status(client, clinic_headers, patient):
    created = _create_appointment(client, clinic_headers, patient).json()
    res = client.patch(
        f"/appointments/{created['id']}", headers=clinic_headers, json={"status": "completed"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


def test_patch_appointment_invalid_status(client, clinic_headers, patient):
    created = _create_appointment(client, clinic_headers, patient).json()
    res = client.patch(
        f"/appointments/{created['id']}", headers=clinic_headers, json={"status": "wat"}
    )
    assert res.status_code == 409


def test_cancel_appointment(client, clinic_headers, patient):
    created = _create_appointment(client, clinic_headers, patient).json()
    res = client.delete(f"/appointments/{created['id']}", headers=clinic_headers)
    assert res.status_code == 204
    assert (
        client.get(f"/appointments/{created['id']}", headers=clinic_headers).json()["status"]
        == "cancelled"
    )


def test_tenant_isolation(client, clinic_headers, other_clinic_headers, patient):
    created = _create_appointment(client, clinic_headers, patient).json()
    assert client.get(f"/appointments/{created['id']}", headers=other_clinic_headers).status_code == 404
    assert client.get("/appointments", headers=other_clinic_headers).json() == []