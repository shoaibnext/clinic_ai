def _create_lead(client, clinic_headers, **extra):
    payload = {
        "name": "Hassan",
        "phone": "+15550104444",
        "service": "Braces Consultation",
        "source": "whatsapp",
    }
    payload.update(extra)
    return client.post("/leads", headers=clinic_headers, json=payload)


def test_create_lead(client, clinic_headers):
    res = _create_lead(client, clinic_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Hassan"
    assert data["status"] == "new"
    assert data["source"] == "whatsapp"


def test_create_lead_requires_auth(client):
    assert _create_lead(client, {}).status_code == 401


def test_list_leads_and_status_filter(client, clinic_headers):
    assert client.get("/leads", headers=clinic_headers).json() == []
    _create_lead(client, clinic_headers)
    assert len(client.get("/leads", headers=clinic_headers).json()) == 1
    assert len(client.get("/leads", headers=clinic_headers, params={"status": "new"}).json()) == 1
    assert client.get("/leads", headers=clinic_headers, params={"status": "lost"}).json() == []


def test_get_single_lead(client, clinic_headers):
    created = _create_lead(client, clinic_headers).json()
    res = client.get(f"/leads/{created['id']}", headers=clinic_headers)
    assert res.status_code == 200
    assert res.json()["phone"] == "+15550104444"


def test_get_lead_not_found(client, clinic_headers):
    assert client.get("/leads/9999", headers=clinic_headers).status_code == 404


def test_patch_lead(client, clinic_headers):
    created = _create_lead(client, clinic_headers).json()
    res = client.patch(
        f"/leads/{created['id']}", headers=clinic_headers, json={"status": "contacted"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "contacted"


def test_patch_lead_invalid_status(client, clinic_headers):
    created = _create_lead(client, clinic_headers).json()
    res = client.patch(
        f"/leads/{created['id']}", headers=clinic_headers, json={"status": "bogus"}
    )
    assert res.status_code == 409


def test_tenant_isolation(client, clinic_headers, other_clinic_headers):
    created = _create_lead(client, clinic_headers).json()
    assert client.get(f"/leads/{created['id']}", headers=other_clinic_headers).status_code == 404
    assert client.get("/leads", headers=other_clinic_headers).json() == []