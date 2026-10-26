def test_onboard_clinic(client):
    res = client.post(
        "/clinics",
        json={
            "name": "Sunshine Dental",
            "phone": "+15550109999",
            "address": "9 Main St",
            "admin_email": "admin@sunshine.test",
            "admin_password": "Sunshine123!",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["slug"] == "sunshine-dental"
    assert data["name"] == "Sunshine Dental"
    assert data["api_key"].startswith("ck_")
    assert data["status"] == "active"


def test_onboard_duplicate_slug_conflict(client):
    client.post(
        "/clinics",
        json={"name": "Twilight Clinic", "admin_email": "a@twilight.test", "admin_password": "Pass1234!"},
    )
    res = client.post(
        "/clinics",
        json={"name": "Twilight Clinic", "admin_email": "b@twilight.test", "admin_password": "Pass1234!"},
    )
    assert res.status_code == 409
    assert "already in use" in res.json()["detail"]


def test_get_me_with_api_key(client, clinic, clinic_headers):
    res = client.get("/clinics/me", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["id"] == clinic.id
    assert res.json()["name"] == clinic.name


def test_get_me_requires_auth(client, clinic):
    assert client.get("/clinics/me").status_code == 401
    assert client.get("/clinics/me", headers={"X-API-Key": "bogus"}).status_code == 401


def test_set_whatsapp_phone(client, clinic):
    res = client.post(
        f"/clinics/{clinic.id}/whatsapp-phone",
        params={"phone_number_id": "WHATSAPP_987654"},
    )
    assert res.status_code == 200
    assert res.json()["whatsapp_phone_number_id"] == "WHATSAPP_987654"


def test_set_whatsapp_phone_not_found(client, clinic):
    res = client.post("/clinics/999999/whatsapp-phone", params={"phone_number_id": "X"})
    assert res.status_code == 404