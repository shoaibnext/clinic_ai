from app.services import conversation_service


def _make_conversation(db_session, clinic, patient):
    return conversation_service.get_or_create_conversation(
        db_session, clinic, patient, channel="whatsapp"
    )


def test_list_conversations_empty(client, clinic_headers):
    assert client.get("/conversations", headers=clinic_headers).json() == []


def test_list_conversations(client, db_session, clinic_headers, clinic, patient):
    _make_conversation(db_session, clinic, patient)
    res = client.get("/conversations", headers=clinic_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["status"] == "ai_active"


def _seed_conversation_with_messages(db_session, clinic, patient):
    conversation = _make_conversation(db_session, clinic, patient)
    conversation_service.add_message(db_session, clinic, conversation.id, direction="in", body="Hello")
    conversation_service.add_message(
        db_session, clinic, conversation.id, direction="out", body="Hi, how can I help?"
    )
    db_session.commit()
    return conversation


def test_get_conversation_detail(client, db_session, clinic_headers, clinic, patient):
    conversation = _seed_conversation_with_messages(db_session, clinic, patient)
    res = client.get(f"/conversations/{conversation.id}", headers=clinic_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["patient"]["id"] == patient.id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["direction"] == "in"


def test_get_conversation_not_found(client, clinic_headers):
    assert client.get("/conversations/55555", headers=clinic_headers).status_code == 404


def test_patch_conversation_to_human_active(client, db_session, clinic_headers, clinic, patient):
    conversation = _make_conversation(db_session, clinic, patient)
    res = client.patch(
        f"/conversations/{conversation.id}",
        headers=clinic_headers,
        json={"status": "human_active"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "human_active"


def test_patch_conversation_invalid_status(client, db_session, clinic_headers, clinic, patient):
    conversation = _make_conversation(db_session, clinic, patient)
    res = client.patch(
        f"/conversations/{conversation.id}", headers=clinic_headers, json={"status": "warp"}
    )
    assert res.status_code == 409


def test_patch_conversation_not_found(client, clinic_headers):
    res = client.patch(
        "/conversations/55555", headers=clinic_headers, json={"status": "resolved"}
    )
    assert res.status_code == 404


def test_tenant_isolation(client, db_session, clinic, other_clinic, patient):
    conversation = _make_conversation(db_session, clinic, patient)
    res = client.get(
        f"/conversations/{conversation.id}",
        headers={"X-API-Key": other_clinic.api_key},
    )
    assert res.status_code == 404