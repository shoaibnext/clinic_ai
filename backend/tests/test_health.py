def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert "service" in body


def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["message"] == "Clinic AI Receptionist API"
    assert body["version"] == "1.0.0"
    assert "service" in body


def test_openapi_docs_available(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert "/health" in paths
    assert "/auth/login" in paths
    assert "/clinics" in paths
    assert "/ai/chat" in paths
    assert "/whatsapp/webhook" in paths