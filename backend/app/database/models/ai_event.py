from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class AIEvent(Base):
    __tablename__ = "ai_events"

    # event_type values: intent_detection, rag_search, llm_request, llm_response,
    #                     tool_call, handoff, safety, error
    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))
    input_data: Mapped[dict | None] = mapped_column(JSON)
    output_data: Mapped[dict | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())