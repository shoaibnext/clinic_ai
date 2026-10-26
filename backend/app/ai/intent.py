"""Structured intent detection (build plan 5.2 / 5.4)."""

import json
import re
import time
from dataclasses import dataclass, field

from app.ai.client import complete
from app.ai.events import record_ai_event
from app.ai.prompts import intent_extraction_prompt

KNOWN_INTENTS = {
    "FAQ",
    "BOOK_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "CANCEL_APPOINTMENT",
    "CHECK_AVAILABILITY",
    "PROVIDE_PATIENT_INFO",
    "HUMAN_HANDOFF",
    "EMERGENCY",
    "UNKNOWN",
}


def rule_based_intent(
    message: str,
    services: list[str] | None = None,  # noqa: ARG001
    doctors: list[str] | None = None,  # noqa: ARG001
) -> str | None:
    """Deterministic keyword fallback for intent detection.

    Used when the LLM returns UNKNOWN or the provider call fails (rate limits,
    free-tier outages). Simple keyword triggers; never fires on generic chat.
    """
    low = message.lower()
    if any(w in low for w in ("emergency", "urgent", "bleeding", "ambulance", "chest pain", "severe pain", "dying")):
        return "EMERGENCY"
    if any(w in low for w in ("talk to a human", "speak to a human", "speak to someone", "staff member", "agent", "complaint", "refund", "manager")):
        return "HUMAN_HANDOFF"
    if any(w in low for w in ("reschedule", "reschdule", "move my appointment", "change my appointment")):
        return "RESCHEDULE_APPOINTMENT"
    if any(w in low for w in ("cancel my appointment", "cancel my booking", "cancellation", "cancel appointment")):
        return "CANCEL_APPOINTMENT"
    if any(w in low for w in ("book", "appointment", "schedule", "reserve", "booking", "slot today")):
        return "BOOK_APPOINTMENT"
    if any(w in low for w in ("available", "availability", "free slot", "which date", "opening hour", "when do you open", "when are you open", "working day", "open tomorrow", "open today")):
        return "CHECK_AVAILABILITY"
    if any(w in low for w in ("my name is", "my number is", "my phone", "contact number")):
        return "PROVIDE_PATIENT_INFO"
    return None


@dataclass
class IntentResult:
    intent: str = "UNKNOWN"
    confidence: float = 0.0
    entities: dict = field(default_factory=dict)


def _parse_json(text: str) -> dict | None:
    text = text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


async def detect_intent(
    clinic,
    message: str,
    *,
    services: list[str] | None = None,
    doctors: list[str] | None = None,
    db=None,
    conversation_id: int | None = None,
) -> IntentResult:
    start = time.monotonic()
    system_prompt = intent_extraction_prompt(clinic.name, services or [], doctors or [])
    try:
        raw = await complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        if db is not None:
            record_ai_event(
                db,
                clinic_id=clinic.id,
                conversation_id=conversation_id,
                event_type="error",
                input_data={"step": "intent_detection", "message": message},
                output_data={"error": str(exc)},
            )
        fallback = rule_based_intent(message, services, doctors)
        return IntentResult(intent=fallback or "UNKNOWN", confidence=0.7 if fallback else 0.0)

    data = _parse_json(raw) or {}
    intent = str(data.get("intent", "UNKNOWN")).upper()
    if intent not in KNOWN_INTENTS:
        intent = "UNKNOWN"
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    # Weak/uncertain result (or provider hiccup) -> deterministic fallback.
    if intent == "UNKNOWN":
        fallback = rule_based_intent(message, services, doctors)
        if fallback:
            intent = fallback
            confidence = max(confidence, 0.6)

    entities = data.get("entities") or {}
    if not isinstance(entities, dict):
        entities = {}

    result = IntentResult(
        intent=intent,
        confidence=min(max(confidence, 0.0), 1.0),
        entities={
            "service": entities.get("service") or None,
            "doctor": entities.get("doctor") or None,
            "date": entities.get("date") or None,
            "time": entities.get("time") or None,
            "patient_name": entities.get("patient_name") or None,
        },
    )

    if db is not None:
        record_ai_event(
            db,
            clinic_id=clinic.id,
            conversation_id=conversation_id,
            event_type="intent_detection",
            input_data={"message": message},
            output_data={
                "intent": result.intent,
                "confidence": result.confidence,
                "entities": result.entities,
            },
            latency_ms=int((time.monotonic() - start) * 1000),
        )
    return result