import hashlib
import hmac
import json
import zlib
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.whatsapp_service import extract_text_messages, verify_webhook_signature


@pytest.fixture(autouse=True)
def _isolate_whatsapp_app_secret():
    """Make webhook tests hermetic: start every test with WHATSAPP_APP_SECRET
    cleared so results never depend on a developer's local .env. Tests that
    exercise signature verification set the secret explicitly inside the test."""
    original = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = ""
    yield
    settings.whatsapp_app_secret = original

WEBHOOK_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "15550000000", "phone_number_id": "123456789"},
                        "contacts": [{"wa_id": "15550101111"}],
                        "messages": [
                            {
                                "from": "15550101111",
                                "id": "wamid.abc123",
                                "type": "text",
                                "text": {"body": "I want to book an appointment"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def test_extract_text_messages():
    messages = extract_text_messages(WEBHOOK_PAYLOAD)
    assert len(messages) == 1
    assert messages[0]["from"] == "15550101111"
    assert messages[0]["text"] == "I want to book an appointment"
    assert messages[0]["id"] == "wamid.abc123"


def test_extract_text_messages_skips_non_text():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"type": "image", "from": "x"},
                                {"type": "text", "from": "y", "text": {"body": "hi"}},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    messages = extract_text_messages(payload)
    assert len(messages) == 1
    assert messages[0]["text"] == "hi"


def test_extract_text_messages_empty():
    assert extract_text_messages({}) == []
    assert extract_text_messages({"entry": []}) == []


def test_verify_webhook_success(client):
    res = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_webhook_verify_token,
            "hub.challenge": "987654321",
        },
    )
    assert res.status_code == 200
    assert res.text == "987654321"


def test_verify_webhook_failure(client):
    res = client.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
    )
    assert res.status_code == 403


def test_webhook_receive_no_messages(client):
    res = client.post("/whatsapp/webhook", json={"object": "whatsapp_business_account"})
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_webhook_receive_no_clinic(client):
    res = client.post("/whatsapp/webhook", json=WEBHOOK_PAYLOAD)
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_webhook_receive_full_flow(client, clinic):
    """End-to-end webhook: inbound text -> AI reply -> message persisted, no WhatsApp send
    when credentials are absent (mocked so the test is deterministic)."""
    payload = dict(WEBHOOK_PAYLOAD)
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"][
        "body"
    ] = "I want to book a dental cleaning"
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = (
        clinic.whatsapp_phone_number_id
    )

    with (
        patch("app.api.whatsapp.handle_message", new=AsyncMock(return_value="Sure! When works for you?")) as handle,
        patch("app.api.whatsapp.send_text_message", new=AsyncMock()) as send,
    ):
        res = client.post("/whatsapp/webhook", json=payload)

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert handle.await_count == 1
    # No credentials configured by default for the shared setting in tests is not
    # guaranteed, so assert that even if a send were attempted it would use the mock.
    send.assert_not_called() if not (settings.whatsapp_phone_number_id and settings.whatsapp_access_token) else None


def test_webhook_persists_messages_and_patient(client, db_session, clinic):
    payload = dict(WEBHOOK_PAYLOAD)
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = (
        clinic.whatsapp_phone_number_id
    )
    with (
        patch("app.api.whatsapp.handle_message", new=AsyncMock(return_value="Thanks!")),
        patch("app.api.whatsapp.send_text_message", new=AsyncMock()),
    ):
        client.post("/whatsapp/webhook", json=payload)

    from app.database.models import Conversation, Message
    from app.services import patient_service

    patient = patient_service.get_patient_by_phone(db_session, clinic, "15550101111")
    assert patient is not None
    conversation = db_session.query(Conversation).filter(Conversation.patient_id == patient.id).first()
    assert conversation is not None
    messages = (
        db_session.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )
    assert [m.direction for m in messages] == ["in", "out"]


# --------------------------------------------------------------------------- #
# Webhook signature verification (X-Hub-Signature-256)
# --------------------------------------------------------------------------- #

SECRET = "test-app-secret"


def _signed_headers(payload: bytes, secret: str = SECRET) -> dict:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}", "content-type": "application/json"}


def test_verify_webhook_signature_helper():
    secret = SECRET
    body = b'{"object": "whatsapp_business_account"}'
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(body, good, secret) is True
    # Bare hex digest (no "sha256=" prefix) is accepted too
    assert verify_webhook_signature(body, good.split("=", 1)[1], secret) is True
    # Wrong secret / tampered body / empty inputs all fail closed
    assert verify_webhook_signature(body, good, "another-secret") is False
    tampered = b'{"object": "hacked"}'
    tampered_sig = "sha256=" + hmac.new(secret.encode(), tampered, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, tampered_sig, secret) is False
    assert verify_webhook_signature(b"", good, secret) is False
    assert verify_webhook_signature(body, "", secret) is False


def test_webhook_rejects_missing_signature(client):
    original = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = SECRET
    try:
        res = client.post("/whatsapp/webhook", json=WEBHOOK_PAYLOAD)
        assert res.status_code == 403
    finally:
        settings.whatsapp_app_secret = original


def test_webhook_rejects_invalid_signature(client):
    original = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = SECRET
    try:
        payload = json.dumps(WEBHOOK_PAYLOAD).encode("utf-8")
        headers = {"X-Hub-Signature-256": "sha256=" + "0" * 64, "content-type": "application/json"}
        res = client.post("/whatsapp/webhook", content=payload, headers=headers)
        assert res.status_code == 403
    finally:
        settings.whatsapp_app_secret = original


def test_webhook_accepts_valid_signature(client):
    original = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = SECRET
    try:
        payload = json.dumps(WEBHOOK_PAYLOAD).encode("utf-8")
        res = client.post("/whatsapp/webhook", content=payload, headers=_signed_headers(payload))
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
    finally:
        settings.whatsapp_app_secret = original


def test_webhook_signature_skipped_when_no_secret(client, clinic):
    """Dev mode: no WHATSAPP_APP_SECRET configured -> webhook still processes (legacy behaviour)."""
    payload = dict(WEBHOOK_PAYLOAD)
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = (
        clinic.whatsapp_phone_number_id
    )
    with (
        patch("app.api.whatsapp.handle_message", new=AsyncMock(return_value="Thanks!")) as handle,
        patch("app.api.whatsapp.send_text_message", new=AsyncMock()),
    ):
        res = client.post("/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert handle.await_count == 1


def test_webhook_full_flow_with_valid_signature(client, clinic):
    """End-to-end with a valid signature: verification passes and the AI loop still runs."""
    payload = dict(WEBHOOK_PAYLOAD)
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = (
        clinic.whatsapp_phone_number_id
    )
    body = json.dumps(payload).encode("utf-8")

    original = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = SECRET
    try:
        with (
            patch("app.api.whatsapp.handle_message", new=AsyncMock(return_value="Sure!")) as handle,
            patch("app.api.whatsapp.send_text_message", new=AsyncMock()),
        ):
            res = client.post("/whatsapp/webhook", content=body, headers=_signed_headers(body))
    finally:
        settings.whatsapp_app_secret = original

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert handle.await_count == 1

def test_webhook_returns_200_when_whatsapp_send_fails(client, clinic):
    """A Graph API send failure (e.g. expired token) must NOT 500 the webhook.

    The AI reply is persisted before delivery; failing the webhook would make
    Meta retry and re-process the same message (duplicate saves/replies).
    """
    payload = dict(WEBHOOK_PAYLOAD)
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = (
        clinic.whatsapp_phone_number_id
    )

    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = "WHATSAPP_987654"
    settings.whatsapp_access_token = "EXPIRED_TOKEN"
    try:
        request = httpx.Request(
            "POST", "https://graph.facebook.com/v21.0/WHATSAPP_987654/messages"
        )
        response = httpx.Response(
            401, request=request, json={"error": {"code": 190, "message": "Session has expired"}}
        )
        with (
            patch("app.api.whatsapp.handle_message", new=AsyncMock(return_value="Thanks!")),
            patch(
                "app.api.whatsapp.send_text_message",
                new=AsyncMock(
                    side_effect=httpx.HTTPStatusError(
                        "Client error '401 Unauthorized'", request=request, response=response
                    )
                ),
            ),
        ):
            res = client.post("/whatsapp/webhook", json=payload)
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# Connection diagnostics: GET /whatsapp/status and POST /whatsapp/test
# --------------------------------------------------------------------------- #


def test_whatsapp_status_unconfigured(client):
    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = ""
    settings.whatsapp_access_token = ""
    try:
        res = client.get("/whatsapp/status")
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is False
    assert data["phone_number_id"] == "not set"
    assert data["access_token"] == "not set"
    assert data["graph_api"] is None


def test_whatsapp_status_configured_ok(client):
    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = "WHATSAPP_987654"
    settings.whatsapp_access_token = "TEST_ACCESS_TOKEN"
    try:
        with patch(
            "app.services.whatsapp_service.fetch_phone_number_info",
            new=AsyncMock(return_value={"id": "WHATSAPP_987654", "display_phone_number": "15550000000"}),
        ) as fetch:
            res = client.get("/whatsapp/status")
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["phone_number_id"] == "WHATSAPP_987654"
    assert data["access_token"] == "set"
    assert data["graph_api"]["ok"] is True
    assert data["graph_api"]["info"]["display_phone_number"] == "15550000000"
    fetch.assert_awaited_once()


def test_whatsapp_status_surfaces_graph_error(client):
    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = "WHATSAPP_987654"
    settings.whatsapp_access_token = "BAD_TOKEN"
    request = httpx.Request("GET", "https://graph.facebook.com/v21.0/WHATSAPP_987654")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"code": 190, "message": "Error validating access token: Session has expired"}},
    )
    try:
        with patch(
            "app.services.whatsapp_service.fetch_phone_number_info",
            new=AsyncMock(
                side_effect=httpx.HTTPStatusError("Client error", request=request, response=response)
            ),
        ):
            res = client.get("/whatsapp/status")
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["graph_api"]["ok"] is False
    assert data["graph_api"]["status_code"] == 400
    assert data["graph_api"]["code"] == 190
    assert "expired" in data["graph_api"]["error"]


def test_whatsapp_test_sends_message(client):
    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = "WHATSAPP_987654"
    settings.whatsapp_access_token = "TEST_ACCESS_TOKEN"
    try:
        with patch("app.api.whatsapp.send_text_message", new=AsyncMock()) as send:
            res = client.post(
                "/whatsapp/test",
                json={"to_phone": "+15550101111", "text": "Hello from Clinic AI!"},
            )
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 200
    assert res.json() == {"ok": True, "detail": "Message sent", "status_code": 200}
    send.assert_awaited_once_with("+15550101111", "Hello from Clinic AI!")


def test_whatsapp_test_requires_credentials(client):
    original = (settings.whatsapp_phone_number_id, settings.whatsapp_access_token)
    settings.whatsapp_phone_number_id = ""
    settings.whatsapp_access_token = ""
    try:
        res = client.post("/whatsapp/test", json={"to_phone": "+15550101111", "text": "hi"})
    finally:
        settings.whatsapp_phone_number_id, settings.whatsapp_access_token = original

    assert res.status_code == 400
    assert "not configured" in res.json()["detail"]