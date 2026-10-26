def _create_doctor(client, clinic_headers, **extra):
    payload = {
        "name": "Dr. Khan",
        "title": "Dentist",
        "specialty": "Dentistry",
        "service_ids": [],
    }
    payload.update(extra)
    return client.post("/doctors", headers=clinic_headers, json=payload)


def test_create_doctor(client, clinic_headers, service):
    res = _create_doctor(client, clinic_headers, service_ids=[service.id])
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Dr. Khan"
    assert data["clinic_id"] == service.clinic_id
    assert data["is_active"] is True


def test_create_doctor_requires_auth(client, service):
    res = _create_doctor(client, {})
    assert res.status_code == 401


def test_create_doctor_with_invalid_service_propagates(client, clinic_headers):
    # create_doctor stores the link row but does not validate service existence,
    # so the doctor itself is created successfully.
    res = _create_doctor(client, clinic_headers, service_ids=[999999])
    assert res.status_code == 201


def test_list_doctors(client, clinic_headers):
    assert client.get("/doctors", headers=clinic_headers).json() == []
    _create_doctor(client, clinic_headers)
    res = client.get("/doctors", headers=clinic_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_single_doctor(client, clinic_headers):
    created = _create_doctor(client, clinic_headers).json()
    res = client.get(f"/doctors/{created['id']}", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Dr. Khan"


def test_get_doctor_not_found(client, clinic_headers):
    res = client.get("/doctors/111111", headers=clinic_headers)
    assert res.status_code == 404


def test_get_doctor_services(client, clinic_headers, service):
    created = _create_doctor(client, clinic_headers, service_ids=[service.id]).json()
    res = client.get(f"/doctors/{created['id']}/services", headers=clinic_headers)
    assert res.status_code == 200
    ids = [s["id"] for s in res.json()]
    assert service.id in ids


def test_tenant_isolation(client, clinic_headers, other_clinic_headers):
    created = _create_doctor(client, clinic_headers).json()
    # Clinic B cannot see Clinic A's doctor.
    res = client.get(f"/doctors/{created['id']}", headers=other_clinic_headers)
    assert res.status_code == 404
    assert client.get("/doctors", headers=other_clinic_headers).json() == []