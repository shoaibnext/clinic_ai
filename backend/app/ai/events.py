"""AI event logging (build plan 5.12).

event_type values: intent_detection, rag_search, llm_request, llm_response,
tool_call, handoff, safety, error
"""
import time
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.database.models import AIEvent


def record_ai_event(
    db: Session,
    *,
    clinic_id: int,
    conversation_id: int | None = None,
    event_type: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    latency_ms: int | None = None,
) -> None:
    """Persist an AI event. Never lets logging break the main flow."""
    try:
        db.add(
            AIEvent(
                clinic_id=clinic_id,
                conversation_id=conversation_id,
                event_type=event_type,
                input_data=input_data,
                output_data=output_data,
                latency_ms=latency_ms,
            )
        )
        db.flush()
    except Exception:
        db.rollback()


@contextmanager
def timed_event(db: Session, *, clinic_id: int, conversation_id: int | None, event_type: str, input_data: dict | None = None) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        try:
            latency_ms = int((time.monotonic() - start) * 1000)
            record_ai_event(
                db,
                clinic_id=clinic_id,
                conversation_id=conversation_id,
                event_type=event_type,
                input_data=input_data,
                latency_ms=latency_ms,
            )
        except Exception:
            pass