from pydantic import BaseModel, Field


class TestChatRequest(BaseModel):
    """Level-1 endpoint from build plan Step 5.1."""

    clinic_name: str = Field(min_length=1)
    message: str = Field(min_length=1)


class TestChatResponse(BaseModel):
    response: str


class ChatRequest(BaseModel):
    """Full AI receptionist loop (build plan Step 5)."""

    message: str = Field(min_length=1)
    clinic_slug: str | None = Field(default=None, description="Identify the clinic by slug")
    clinic_id: int | None = Field(default=None, description="...or by id")
    conversation_id: int | None = Field(default=None)


class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    conversation_id: int | None = None