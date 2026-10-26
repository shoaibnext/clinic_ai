import pytest

from app.ai.intent import KNOWN_INTENTS, _parse_json, detect_intent, rule_based_intent


class _Clinic:
    id = 1
    name = "ABC Dental Clinic"


def test_parse_json_plain():
    assert _parse_json('{"intent": "FAQ", "confidence": 0.9}') == {
        "intent": "FAQ",
        "confidence": 0.9,
    }


def test_parse_json_code_fence():
    raw = '```json\n{"intent": "FAQ", "confidence": 0.9}\n```'
    assert _parse_json(raw)["intent"] == "FAQ"


def test_parse_json_embedded():
    assert _parse_json('prefix {"intent": "FAQ"} suffix')["intent"] == "FAQ"


def test_parse_json_invalid():
    assert _parse_json("not json at all") is None


def test_known_intents():
    assert "FAQ" in KNOWN_INTENTS
    assert "BOOK_APPOINTMENT" in KNOWN_INTENTS
    assert "CANCEL_APPOINTMENT" in KNOWN_INTENTS
    assert "RESCHEDULE_APPOINTMENT" in KNOWN_INTENTS
    assert "CHECK_AVAILABILITY" in KNOWN_INTENTS
    assert "PROVIDE_PATIENT_INFO" in KNOWN_INTENTS
    assert "HUMAN_HANDOFF" in KNOWN_INTENTS
    assert "EMERGENCY" in KNOWN_INTENTS
    assert "UNKNOWN" in KNOWN_INTENTS


async def _fake_complete(messages, **kwargs):
    last = messages[-1]["content"]
    if "book" in last:
        return (
            '{"intent": "BOOK_APPOINTMENT", "confidence": 0.97, '
            '"entities": {"service": "dental cleaning", "doctor": null, '
            '"date": "2026-09-15", "time": null, "patient_name": null}}'
        )
    if "open" in last:
        return '{"intent": "FAQ", "confidence": 0.99, "entities": {}}'
    return '{"intent": "UNKNOWN", "confidence": 0.2, "entities": {}}'


@pytest.mark.asyncio
async def test_detect_intent_booking(monkeypatch):
    monkeypatch.setattr("app.ai.intent.complete", _fake_complete)
    result = await detect_intent(
        _Clinic(), "I want to book a dental cleaning", services=["Dental Cleaning"], doctors=[]
    )
    assert result.intent == "BOOK_APPOINTMENT"
    assert result.confidence == pytest.approx(0.97)
    assert result.entities["service"] == "dental cleaning"
    assert result.entities["date"] == "2026-09-15"


@pytest.mark.asyncio
async def test_detect_intent_faq(monkeypatch):
    monkeypatch.setattr("app.ai.intent.complete", _fake_complete)
    result = await detect_intent(_Clinic(), "What are your opening hours?")
    assert result.intent == "FAQ"


@pytest.mark.asyncio
async def test_detect_intent_unknown_falls_back(monkeypatch):
    async def broken(messages, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.ai.intent.complete", broken)
    result = await detect_intent(_Clinic(), "hello")
    assert result.intent == "UNKNOWN"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_detect_intent_booking_fallback_on_llm_error(monkeypatch):
    """Provider outages must not silently break obvious booking requests."""

    async def broken(messages, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.ai.intent.complete", broken)
    result = await detect_intent(_Clinic(), "I want to book an appointment tomorrow")
    assert result.intent == "BOOK_APPOINTMENT"
    assert result.confidence >= 0.6


def test_rule_based_intent_triggers():
    assert rule_based_intent("I want to book an appointment") == "BOOK_APPOINTMENT"
    assert rule_based_intent("what times are available tomorrow") == "CHECK_AVAILABILITY"
    assert rule_based_intent("please cancel my appointment") == "CANCEL_APPOINTMENT"
    assert rule_based_intent("I need to reschedule") == "RESCHEDULE_APPOINTMENT"
    assert rule_based_intent("this is an emergency, help") == "EMERGENCY"
    assert rule_based_intent("my name is Ali, my number is 0300") == "PROVIDE_PATIENT_INFO"


def test_rule_based_intent_returns_none_for_chat():
    assert rule_based_intent("hello") is None
    assert rule_based_intent("I am feeling okay today") is None


@pytest.mark.asyncio
async def test_detect_intent_clamps_confidence(monkeypatch):
    async def high(messages, **kwargs):
        return '{"intent": "FAQ", "confidence": 5.0, "entities": {}}'

    monkeypatch.setattr("app.ai.intent.complete", high)
    result = await detect_intent(_Clinic(), "hello")
    assert result.confidence <= 1.0


@pytest.mark.asyncio
async def test_detect_intent_rejects_unknown_intent(monkeypatch):
    async def bad_intent(messages, **kwargs):
        return '{"intent": "TELEPORT", "confidence": 0.9, "entities": {}}'

    monkeypatch.setattr("app.ai.intent.complete", bad_intent)
    result = await detect_intent(_Clinic(), "hello")
    assert result.intent == "UNKNOWN"