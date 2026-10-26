from app.ai.safety import (
    emergency_response,
    medical_advice_response,
    safety_precheck,
    wants_human_handoff,
)


class _Clinic:
    def __init__(self, phone=None, emergency_instructions=None):
        self.phone = phone
        self.emergency_instructions = emergency_instructions


def test_safety_precheck_safe():
    result = safety_precheck("What are your opening hours?")
    assert result.level == "safe"


def test_safety_precheck_emergency():
    result = safety_precheck("I have severe chest pain and difficulty breathing")
    assert result.level == "emergency"
    assert result.reason


def test_safety_precheck_medical_advice():
    result = safety_precheck("What medicine should I take for a headache?")
    assert result.level == "medical_advice"


def test_safety_precheck_emergency_wins_over_advice():
    result = safety_precheck("Severe chest pain, what medicine should I take?")
    assert result.level == "emergency"


def test_emergency_response_uses_clinic_instructions():
    clinic = _Clinic(phone="+15551234567", emergency_instructions="Call 112 right now.")
    text = emergency_response(clinic)
    assert "Call 112 right now." in text
    assert "+15551234567" in text
    assert "not" in text.lower() and "doctor" in text.lower()


def test_medical_advice_response_declines():
    text = medical_advice_response(_Clinic(phone="+15551234567"))
    assert "not able to give medical advice" in text
    assert "+15551234567" in text


def test_wants_human_handoff():
    assert wants_human_handoff("I want to talk to a human")
    assert wants_human_handoff("I would like to speak to staff please")
    assert wants_human_handoff("This is a complaint")
    assert not wants_human_handoff("What time do you close?")