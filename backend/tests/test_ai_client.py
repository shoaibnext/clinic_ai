"""Regression tests for the LLM client provider routing and graceful errors.

The live smoke test caught two real bugs:
1. get_model() returned the OpenAI default ("gpt-4o-mini") even when the
   provider is Groq, because openai_model has a non-empty default that
   short-circuited `openai_model or groq_model`.
2. LLM/provider failures surfaced as raw 500 instead of a clean 502.
"""
import pytest

from app.ai import client as ai_client
from app.core.config import settings


def _reset_client_cache():
    ai_client._llm = None


def test_get_model_uses_groq_model_when_provider_groq(monkeypatch):
    # openai_model's non-empty default used to shadow the Groq model
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    _reset_client_cache()
    assert ai_client.get_model() == "llama-3.3-70b-versatile"


def test_get_model_uses_openai_model_when_provider_openai(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")
    _reset_client_cache()
    assert ai_client.get_model() == "gpt-4o-mini"


def test_active_credentials_groq(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_base_url", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "groq_api_key", "gk_abc")
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "openai_base_url", "")  # must NOT win
    monkeypatch.setattr(settings, "openai_api_key", "")
    url, key, model = ai_client._active_credentials()
    assert url == "https://api.groq.com/openai/v1"
    assert key == "gk_abc"
    assert model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_complete_uses_configured_provider(monkeypatch):
    """The chat completion call must be issued to the active provider's client."""
    monkeypatch.setattr(settings, "llm_provider", "groq")
    _reset_client_cache()

    captured = {}

    class _FakeCompletionsResource:
        def __init__(self):
            self.captured = captured

        async def create(self, **kwargs):
            self.captured["call_kwargs"] = kwargs
            return type(
                "R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "hi"})()})()]}
            )()

    class _FakeChatNamespace:
        completions = _FakeCompletionsResource()

    class _FakeClient:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.chat = _FakeChatNamespace()

    monkeypatch.setattr(ai_client, "AsyncOpenAI", _FakeClient)
    out = await ai_client.complete(
        [{"role": "user", "content": "hello"}], response_format={"type": "json_object"}
    )
    assert out == "hi"
    assert captured["call_kwargs"]["model"] == settings.groq_model
    assert captured["call_kwargs"]["response_format"] == {"type": "json_object"}


def test_test_chat_returns_502_on_llm_failure(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("Invalid API Key")

    monkeypatch.setattr("app.api.ai.process_message", boom)
    r = client.post("/test-chat", json={"clinic_name": "X", "message": "hi"})
    assert r.status_code == 502
    assert "AI service unavailable" in r.json()["detail"]


def test_ai_chat_returns_502_on_llm_failure(client, clinic, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("Provider outage")

    monkeypatch.setattr("app.api.ai.handle_message", boom)
    r = client.post("/ai/chat", json={"clinic_slug": clinic.slug, "message": "hi"})
    assert r.status_code == 502
    assert "AI service unavailable" in r.json()["detail"]


def test_ai_chat_unknown_clinic_404(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("should not run")

    monkeypatch.setattr("app.api.ai.handle_message", boom)
    r = client.post("/ai/chat", json={"clinic_slug": "does-not-exist", "message": "hi"})
    assert r.status_code == 404


def test_ai_test_reports_configured_model(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")
    _reset_client_cache()
    r = client.get("/ai/test")
    assert r.status_code == 200
    assert r.json()["status"] == "configured"
    assert r.json()["model"] == "llama-3.3-70b-versatile"


# --------------------------------------------------------------------------- #
# OpenRouter provider
# --------------------------------------------------------------------------- #
def test_get_model_uses_openrouter_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "meta-llama/llama-3.3-70b-instruct:free")
    _reset_client_cache()
    assert ai_client.get_model() == "meta-llama/llama-3.3-70b-instruct:free"


def test_active_credentials_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-v1-test")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o-mini")
    url, key, model = ai_client._active_credentials()
    assert url == "https://openrouter.ai/api/v1"
    assert key == "sk-or-v1-test"
    assert model == "openai/gpt-4o-mini"


def test_get_llm_openrouter_sends_attribution_headers(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_site_url", "https://example.com")
    monkeypatch.setattr(settings, "openrouter_site_title", "Clinic AI")
    _reset_client_cache()

    captured = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(ai_client, "AsyncOpenAI", _FakeClient)
    ai_client.get_llm()
    assert captured["kwargs"]["base_url"] == settings.openrouter_base_url
    assert captured["kwargs"]["default_headers"]["HTTP-Referer"] == "https://example.com"
    assert captured["kwargs"]["default_headers"]["X-Title"] == "Clinic AI"


# --------------------------------------------------------------------------- #
# Local embeddings fallback (no external key required)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_embed_texts_local_fallback(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    vectors = await ai_client.embed_texts(["dental cleaning cost", "opening hours"])
    assert len(vectors) == 2
    # Similar text produces a higher cosine score than unrelated text.
    a = ai_client.local_embed("how much does dental cleaning cost")
    c = ai_client.cosine_similarity(vectors[0], a)
    unrelated = ai_client.cosine_similarity(vectors[1], a)
    assert c > unrelated


def test_local_embed_is_deterministic_and_normalized():
    v1 = ai_client.local_embed("Dental cleaning at the clinic!")
    v2 = ai_client.local_embed("Dental cleaning at the clinic!")
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)
    assert len(v1) == ai_client._LOCAL_EMBED_DIM
    # Empty-ish text still yields a zero vector without crashing.
    assert ai_client.local_embed("") is not None


def test_local_embed_empty_input():
    # Whitespace-only input has no tokens or bigrams → zero vector (no crash).
    assert ai_client.local_embed("   ") == [0.0] * ai_client._LOCAL_EMBED_DIM


def test_local_embed_stopword_heavy_is_deterministic():
    v1 = ai_client.local_embed("the and or of the")
    v2 = ai_client.local_embed("the and or of the")
    assert v1 == v2  # deterministic even when dominated by stopwords


# --------------------------------------------------------------------------- #
# Provider error handling + model fallback
# --------------------------------------------------------------------------- #
class _ErrResponse:
    """Mimics openai response with choices=None and an error payload."""

    def __init__(self):
        self.choices = None
        self.error = {"message": "Upstream error from Nvidia: Service temporarily overloaded", "code": 502}


class _OkResponse:
    def __init__(self, content="hi"):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content, "reasoning": None})()})()]


@pytest.mark.asyncio
async def test_complete_raises_clear_error_on_choices_none(monkeypatch):
    """When the provider returns choices=None + error, raise a readable error."""
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    _reset_client_cache()

    class _StubCompletions:
        async def create(self, **kwargs):
            return _ErrResponse()

    class _StubClient:
        def __init__(self, **kwargs):
            self.chat = type("ch", (), {"completions": _StubCompletions()})()

    monkeypatch.setattr(ai_client, "get_llm", lambda: _StubClient())
    with pytest.raises(RuntimeError, match="Provider returned an error: Upstream error"):
        await ai_client._complete_once("m", [{"role": "user", "content": "x"}], temperature=0, max_tokens=10, response_format=None)


@pytest.mark.asyncio
async def test_complete_falls_back_to_next_model(monkeypatch):
    """If the primary model errors, the fallback model is used."""
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "primary-model")
    monkeypatch.setattr(settings, "openrouter_fallback_models", ["fallback-model"])
    _reset_client_cache()

    calls = []

    async def fake_once(model, messages, *, temperature, max_tokens, response_format):
        calls.append(model)
        if model == "primary-model":
            raise RuntimeError("Provider returned an error: boom")
        return "fallback reply"

    monkeypatch.setattr(ai_client, "_complete_once", fake_once)
    out = await ai_client.complete([{"role": "user", "content": "x"}])
    assert out == "fallback reply"
    assert calls == ["primary-model", "fallback-model"]


@pytest.mark.asyncio
async def test_complete_retries_without_response_format_when_rejected(monkeypatch):
    """OpenRouter upstreams reject `response_format` with HTTP 400; the client
    retries the call once without it so structured steps (intent) still work."""
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    _reset_client_cache()

    class _RejectingCompletions:
        def __init__(self):
            self.calls: list[dict] = []

        async def create(self, **kwargs):
            self.calls.append(dict(kwargs))
            if "response_format" in self.calls[-1]:
                raise RuntimeError(
                    "Error code: 400 - {'error': {'message': 'The model does not "
                    "support the response_format parameter', 'type': 'invalid_request_error'}}"
                )
            return _OkResponse(content='{"intent": "FAQ", "confidence": 0.9}')

    class _StubClient:
        def __init__(self, **kwargs):
            self.chat = type("ch", (), {"completions": _RejectingCompletions()})()

    monkeypatch.setattr(ai_client, "get_llm", lambda: _StubClient())
    out = await ai_client._complete_once(
        "openrouter-model",
        [{"role": "user", "content": "x"}],
        temperature=0,
        max_tokens=300,
        response_format={"type": "json_object"},
    )
    assert out == '{"intent": "FAQ", "confidence": 0.9}'


def test_completion_models_dedupes_and_orders():
    monkeypatch = None
    # Manual check on the pure function.
    from app.core.config import settings as s

    orig_provider = s.llm_provider
    orig_primary = s.openrouter_model
    orig_fallback = s.openrouter_fallback_models
    try:
        s.llm_provider = "openrouter"
        s.openrouter_model = "a"
        s.openrouter_fallback_models = ["b", "a", "c"]
        assert ai_client._completion_models() == ["a", "b", "c"]
    finally:
        s.llm_provider = orig_provider
        s.openrouter_model = orig_primary
        s.openrouter_fallback_models = orig_fallback