def _create_patient(client, clinic_headers, **extra):
    payload = {"full_name": "Sara Ahmed", "phone_number": "+15550102222", "language": "en"}
    payload.update(extra)
    return client.post("/patients", headers=clinic_headers, json=payload)


def test_create_patient(client, clinic_headers):
    res = _create_patient(client, clinic_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Sara Ahmed"
    assert data["phone_number"] == "+15550102222"


def test_create_patient_requires_auth(client):
    res = _create_patient(client, {})
    assert res.status_code == 401


def test_create_duplicate_phone_conflict(client, clinic_headers):
    _create_patient(client, clinic_headers)
    res = _create_patient(client, clinic_headers, full_name="Another Person")
    assert res.status_code == 409


def test_create_patient_validation(client, clinic_headers):
    res = client.post(
        "/patients", headers=clinic_headers, json={"phone_number": "123"}
    )
    assert res.status_code == 422  # phone_number min_length=5


def test_list_patients(client, clinic_headers):
    assert client.get("/patients", headers=clinic_headers).json() == []
    _create_patient(client, clinic_headers)
    assert len(client.get("/patients", headers=clinic_headers).json()) == 1


def test_get_single_patient(client, clinic_headers):
    created = _create_patient(client, clinic_headers).json()
    res = client.get(f"/patients/{created['id']}", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["phone_number"] == "+15550102222"


def test_get_patient_not_found(client, clinic_headers):
    assert client.get("/patients/999", headers=clinic_headers).status_code == 404


def test_patch_patient(client, clinic_headers):
    created = _create_patient(client, clinic_headers).json()
    res = client.patch(
        f"/patients/{created['id']}",
        headers=clinic_headers,
        json={"full_name": "Sara Updated"},
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Sara Updated"


def test_patch_patient_to_existing_phone_conflict(client, clinic_headers):
    first = _create_patient(client, clinic_headers).json()
    second = _create_patient(client, clinic_headers, phone_number="+15550103333").json()
    res = client.patch(
        f"/patients/{second['id']}",
        headers=clinic_headers,
        json={"phone_number": first["phone_number"]},
    )
    assert res.status_code == 409


def test_delete_patient(client, clinic_headers):
    created = _create_patient(client, clinic_headers).json()
    res = client.delete(f"/patients/{created['id']}", headers=clinic_headers)
    assert res.status_code == 204
    assert client.get(f"/patients/{created['id']}", headers=clinic_headers).status_code == 404


def test_delete_patient_not_found(client, clinic_headers):
    assert client.delete("/patients/999", headers=clinic_headers).status_code == 404


def test_tenant_isolation(client, clinic_headers, other_clinic_headers):
    created = _create_patient(client, clinic_headers).json()
    assert client.get(f"/patients/{created['id']}", headers=other_clinic_headers).status_code == 404
    assert client.get("/patients", headers=other_clinic_headers).json() == []