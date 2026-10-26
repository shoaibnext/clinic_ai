from pydantic import BaseModel, Field


class WhatsAppTestRequest(BaseModel):
    """Payload for POST /whatsapp/test — sends a real outbound message."""

    to_phone: str = Field(min_length=1, description="Recipient phone number (E.164), e.g. +15550101111")
    text: str = Field(min_length=1, max_length=4096, description="Message body to send")


class WhatsAppTestResponse(BaseModel):
    """Result of an outbound test message."""

    ok: bool
    detail: str = ""
    status_code: int | None = None


class WhatsAppStatusResponse(BaseModel):
    """WhatsApp connection/diagnostic state. Secrets are never echoed back —
    only whether each credential is present, plus an optional live Graph API
    validation result when credentials are configured.
    """

    configured: bool
    waba_id: str = ""
    phone_number_id: str = ""
    access_token: str = "not set"
    webhook_verify_token: str = "not set"
    app_secret: str = "not set"
    api_version: str = ""
    graph_api: dict | None = None