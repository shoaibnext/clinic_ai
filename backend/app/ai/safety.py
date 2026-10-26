"""Safety layer (build plan 5.8). The receptionist never diagnoses or prescribes."""

from dataclasses import dataclass

EMERGENCY_TERMS = [
    "emergency",
    "emergencies",
    "severe chest pain",
    "chest pain",
    "heart attack",
    "can't breathe",
    "cannot breathe",
    "not breathing",
    "unconscious",
    "heavy bleeding",
    "uncontrollable bleeding",
    "stroke",
    "suicide",
    "overdose",
    "fainted",
    "seizure",
    "choking",
]

MEDICAL_ADVICE_TERMS = [
    "diagnos",
    "prescribe",
    "medication for",
    "medicine for",
    "treatment for",
    "what should i take",
    "should i take",
    "what medicine",
    "symptoms",
    "test results",
    "is this serious",
    "prescription",
]

HANDOFF_PHRASES = [
    "talk to a human",
    "speak to a human",
    "speak to someone",
    "talk to someone",
    "speak to staff",
    "talk to staff",
    "real person",
    "actual person",
    "human agent",
    "complaint",
    "refund",
]


@dataclass
class SafetyResult:
    level: str  # "safe" | "medical_advice" | "emergency"
    reason: str = ""


def safety_precheck(message: str, intent: str | None = None) -> SafetyResult:
    """Keyword-level pre-check. Production can add an LLM-based classifier."""
    text = f"{message} {intent or ''}".lower()
    for term in EMERGENCY_TERMS:
        if term in text:
            return SafetyResult(level="emergency", reason=term)
    for term in MEDICAL_ADVICE_TERMS:
        if term in text:
            return SafetyResult(level="medical_advice", reason=term)
    return SafetyResult(level="safe")


def emergency_response(clinic) -> str:
    instructions = clinic.emergency_instructions or (
        "Please call emergency services immediately for a medical emergency."
    )
    contact = f" You can also call the clinic at {clinic.phone}." if clinic.phone else ""
    return (
        f"{instructions}\n\n"
        f"I am a receptionist, not a doctor, and I can't give medical advice.{contact} "
        "I have notified the clinic staff to assist you right away."
    )


def medical_advice_response(clinic) -> str:
    contact = f" Our staff can be reached at {clinic.phone}." if clinic.phone else ""
    return (
        "I'm sorry, but I'm an AI receptionist and I'm not able to give medical advice, "
        "diagnose conditions, or recommend treatment. Please consult a doctor for anything "
        f"medical.{contact} I can help you book an appointment or answer clinic questions."
    )


def wants_human_handoff(message: str) -> bool:
    lower = message.lower()
    return any(phrase in lower for phrase in HANDOFF_PHRASES)