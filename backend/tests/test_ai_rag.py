import zlib

import pytest

from app.ai.client import cosine_similarity
from app.ai.rag import retrieve


def test_cosine_identical():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)


def test_cosine_orthogonal():
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)


def test_cosine_empty():
    assert cosine_similarity([], [1]) == 0.0
    assert cosine_similarity([0, 0], [1, 1]) == 0.0


async def _fake_embed(text: str):
    """Simple bag-of-stems vector so related phrases share tokens.

    Uses CRC32 (deterministic across processes) instead of builtin ``hash()``
    which is randomized per interpreter run (PYTHONHASHSEED) and made the
    retrieval ranking order flaky between runs.
    """
    vec = [0.0] * 16
    for word in text.lower().replace(".", "").split():
        stem = word[:-1] if word.endswith(("s", "y")) else word
        vec[zlib.crc32(stem.encode("utf-8")) % 16] += 1.0
    return vec


async def _seed_chunks(db_session, clinic, content_list):
    from app.database.models import Document, DocumentChunk, KnowledgeBase

    kb = KnowledgeBase(clinic_id=clinic.id, name="KB")
    db_session.add(kb)
    db_session.flush()
    doc = Document(clinic_id=clinic.id, knowledge_base_id=kb.id, filename="f.txt")
    db_session.add(doc)
    db_session.flush()
    for i, content in enumerate(content_list):
        db_session.add(
            DocumentChunk(
                clinic_id=clinic.id,
                document_id=doc.id,
                chunk_index=i,
                content=content,
                embedding=await _fake_embed(content),
            )
        )
    db_session.commit()
    return doc


@pytest.mark.asyncio
async def test_retrieve_returns_relevant_chunks(db_session, clinic, monkeypatch):
    monkeypatch.setattr("app.ai.rag.embed_text", _fake_embed)
    await _seed_chunks(
        db_session,
        clinic,
        [
            "Our dental cleaning costs fifty dollars.",
            "We are open Monday to Friday from 9am to 5pm.",
            "Cancellation requires 24 hours notice.",
        ],
    )
    results = await retrieve(db_session, clinic.id, "how much does dental cleaning cost", k=2)
    assert results, "expected at least one result"
    assert "dental cleaning" in results[0]["content"]
    assert all(0.0 <= r["score"] <= 1.0 for r in results)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_retrieve_tenant_isolation(db_session, clinic, other_clinic, monkeypatch):
    monkeypatch.setattr("app.ai.rag.embed_text", _fake_embed)
    await _seed_chunks(db_session, clinic, ["secret clinic A pricing"])
    results = await retrieve(db_session, other_clinic.id, "secret clinic A pricing", k=5)
    assert results == []