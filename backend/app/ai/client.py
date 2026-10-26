"""Provider-independent LLM + embeddings client (build plan 5.1)."""

import hashlib
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings

_llm: AsyncOpenAI | None = None


def _is_response_format_rejection(exc: Exception) -> bool:
    """True when a provider rejected the `response_format` request parameter.

    Free-tier OpenRouter upstreams and several open-weight models return HTTP 400
    for `response_format` even though they can still return the requested JSON in
    plain text. Other runtime failures must not be masked.
    """
    detail = str(exc).lower()
    return "response_format" in detail or "response format" in detail


def _uses_azure() -> bool:
    return (
        settings.llm_provider == "azure"
        and settings.azure_openai_endpoint
        and settings.azure_openai_api_key
    )


def _active_credentials():
    """Return (base_url, api_key, model) for the configured provider.

    `openai_model`/`openai_base_url` have defaults, so they must only be used
    when the provider is explicitly OpenAI — otherwise a Groq setup would
    inadvertently call the Groq API with an OpenAI model string (invalid).
    """
    if settings.llm_provider == "groq":
        return settings.groq_base_url, settings.groq_api_key, settings.groq_model
    if settings.llm_provider == "openai":
        return (
            settings.openai_base_url or "https://api.openai.com/v1",
            settings.openai_api_key,
            settings.openai_model,
        )
    if settings.llm_provider == "openrouter":
        return (
            settings.openrouter_base_url,
            settings.openrouter_api_key,
            settings.openrouter_model,
        )
    # Default fallback: groq when nothing is configured
    return settings.groq_base_url, settings.groq_api_key, settings.groq_model


def get_llm() -> AsyncOpenAI:
    global _llm
    if _llm is None:
        if _uses_azure():
            from openai import AsyncAzureOpenAI

            _llm = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        else:
            base_url, api_key, _model = _active_credentials()
            if settings.llm_provider == "openrouter":
                # OpenRouter attribution headers (their ToS asks for referer+title)
                _llm = AsyncOpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    default_headers={
                        "HTTP-Referer": settings.openrouter_site_url,
                        "X-Title": settings.openrouter_site_title,
                    },
                )
            else:
                _llm = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _llm


def get_model() -> str:
    if _uses_azure():
        return settings.azure_openai_deployment
    return _active_credentials()[2]


async def _complete_once(
    model: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
    response_format: dict[str, str] | None,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format
    try:
        response = await get_llm().chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        # Some providers (e.g. many OpenRouter free-tier upstreams and open-weight
        # models) reject the `response_format` parameter outright (HTTP 400) even
        # though they can return the requested JSON in plain text. Retry once
        # without it; callers that need structured output parse the text reply
        # (e.g. app.ai.intent._parse_json).
        if response_format and _is_response_format_rejection(exc):
            kwargs.pop("response_format", None)
            response = await get_llm().chat.completions.create(**kwargs)
        else:
            raise

    # Some providers (e.g. free-tier OpenRouter upstreams) return a parsed
    # response with choices=None and an `error` payload instead of raising.
    if response.choices is None:
        err = getattr(response, "error", None) or {}
        detail = err.get("message") if isinstance(err, dict) else str(err)
        raise RuntimeError(f"Provider returned an error: {detail or 'unknown error'}")

    if not response.choices:
        return ""

    message = response.choices[0].message
    if message is None:
        return ""
    content = message.content
    # Some reasoning models put the answer only in `message.reasoning`
    # with content=None; fall back to it if present.
    if not content and getattr(message, "reasoning", None):
        content = message.reasoning
    return content or ""


async def complete(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 700,
    response_format: dict[str, str] | None = None,
) -> str:
    """Run a completion, retrying across fallback models on provider errors.

    For OpenRouter the app tries the configured model and any fallbacks so a
    flaky free-tier upstream doesn't break the conversation.
    """
    global _llm
    models = _completion_models()
    last_exc: Exception | None = None
    for model in models:
        try:
            return await _complete_once(
                model, messages, temperature=temperature,
                max_tokens=max_tokens, response_format=response_format,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if model != models[-1]:
                _llm = None  # force a fresh client (per-model attribution)
    if last_exc is not None:
        raise last_exc
    return ""


def _completion_models() -> list[str]:
    """Ordered list of models to try for completions."""
    primary = get_model()
    if settings.llm_provider != "openrouter" or not settings.openrouter_fallback_models:
        return [primary]
    # Deduplicate while preserving order: primary first, then fallbacks.
    seen: set[str] = set()
    ordered = []
    for m in [primary, *settings.openrouter_fallback_models]:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


async def generate_response(
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.2,
) -> str:
    return await complete(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
    )


# --------------------------------------------------------------------------- #
# Embeddings (RAG ingestion + retrieval)
# --------------------------------------------------------------------------- #
# Remote embeddings need an OpenAI/Azure key. OpenRouter does NOT expose an
# embeddings endpoint, so as a fallback we use a lightweight deterministic
# hashing embedder (stable across processes/restarts — NOT Python's randomized
# built-in hash). Quality is below a real model, but it makes RAG work locally
# and in Docker with zero extra credentials.

_LOCAL_EMBED_DIM = 384
_LOCAL_EMBED_STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "with", "at", "our", "your", "we", "you", "i", "it", "be", "as", "by",
}


def _stable_index(token: str, dim: int = _LOCAL_EMBED_DIM) -> int:
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


def _local_tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def local_embed(text: str) -> list[float]:
    """Deterministic bag-of-words + char-bigram embedding, L2-normalized."""
    vector = [0.0] * _LOCAL_EMBED_DIM
    for token in _local_tokenize(text):
        if token not in _LOCAL_EMBED_STOP:
            vector[_stable_index(token)] += 1.0
    alnum = re.sub(r"[^a-z0-9]", "", text.lower())
    for i in range(len(alnum) - 1):
        vector[_stable_index("bg:" + alnum[i:i + 2])] += 0.5
    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if (
        settings.embedding_provider == "azure"
        and settings.azure_openai_endpoint
        and settings.azure_openai_api_key
    ):
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        model = settings.azure_openai_embedding_deployment
        response = await client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]

    if settings.openai_api_key:
        client = AsyncOpenAI(
            base_url=settings.openai_base_url or "https://api.openai.com/v1",
            api_key=settings.openai_api_key,
        )
        response = await client.embeddings.create(model=settings.embedding_model, input=texts)
        return [item.embedding for item in response.data]

    # No remote embedding provider configured — deterministic local fallback.
    return [local_embed(t) for t in texts]


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)