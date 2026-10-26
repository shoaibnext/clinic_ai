def _create_service(client, clinic_headers, **extra):
    payload = {"name": "Dental Cleaning", "duration_minutes": 30, "price": "1500"}
    payload.update(extra)
    return client.post("/services", headers=clinic_headers, json=payload)


def test_create_service(client, clinic_headers):
    res = _create_service(client, clinic_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Dental Cleaning"
    assert data["duration_minutes"] == 30
    assert data["price"] == "1500"
    assert data["is_active"] is True


def test_create_service_requires_auth(client):
    res = _create_service(client, {})
    assert res.status_code == 401


def test_create_service_validation(client, clinic_headers):
    assert client.post(
        "/services", headers=clinic_headers, json={"name": "X", "duration_minutes": 1}
    ).status_code == 422


def test_list_services(client, clinic_headers):
    assert client.get("/services", headers=clinic_headers).json() == []
    _create_service(client, clinic_headers)
    res = client.get("/services", headers=clinic_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_single_service(client, clinic_headers):
    created = _create_service(client, clinic_headers).json()
    res = client.get(f"/services/{created['id']}", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Dental Cleaning"


def test_get_service_not_found(client, clinic_headers):
    assert client.get("/services/99999", headers=clinic_headers).status_code == 404


def test_filter_services_by_doctor(client, clinic_headers, doctor, service):
    res = client.get("/services", headers=clinic_headers, params={"doctor_id": doctor.id})
    assert res.status_code == 200
    assert [s["id"] for s in res.json()] == [service.id]


def test_tenant_isolation(client, clinic_headers, other_clinic_headers):
    created = _create_service(client, clinic_headers).json()
    assert client.get(f"/services/{created['id']}", headers=other_clinic_headers).status_code == 404
    assert client.get("/services", headers=other_clinic_headers).json() == []