"""RAG retrieval (build plan 5.6) with mandatory tenant isolation (5.7)."""

import time

from sqlalchemy.orm import Session

from app.ai.client import cosine_similarity, embed_text
from app.ai.events import record_ai_event
from app.database.models import Document, DocumentChunk


async def ingest_document_chunks(
    db: Session,
    *,
    clinic_id: int,
    document: Document,
    chunks: list[str],
) -> int:
    """Embed and persist chunks for a document. Raises if no embedding provider is configured."""
    start = time.monotonic()
    vectors = await embed_texts_safely(chunks)
    db.query(DocumentChunk).filter(
        DocumentChunk.clinic_id == clinic_id, DocumentChunk.document_id == document.id
    ).delete()
    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        row = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.clinic_id == clinic_id,
                DocumentChunk.document_id == document.id,
                DocumentChunk.chunk_index == index,
            )
            .first()
        )
        if row is None:
            row = DocumentChunk(
                clinic_id=clinic_id,
                document_id=document.id,
                chunk_index=index,
            )
            db.add(row)
        row.content = chunk
        row.embedding = vector
    record_ai_event(
        db,
        clinic_id=clinic_id,
        event_type="rag_ingest",
        input_data={"document_id": document.id, "chunks": len(chunks)},
        latency_ms=int((time.monotonic() - start) * 1000),
    )
    db.commit()
    return len(chunks)


async def embed_texts_safely(texts: list[str]) -> list[list[float]]:
    from app.ai.client import embed_texts

    return await embed_texts(texts)


async def retrieve(
    db: Session,
    clinic_id: int,
    query: str,
    *,
    k: int = 5,
    document_id: int | None = None,
) -> list[dict]:
    """
    Return top-k relevant chunks. Tenant isolation is mandatory: the query is
    always filtered by clinic_id (build plan 5.7).
    """
    start = time.monotonic()
    query_vector = await embed_text(query)

    query_stmt = db.query(DocumentChunk).filter(DocumentChunk.clinic_id == clinic_id)
    if document_id is not None:
        query_stmt = query_stmt.filter(DocumentChunk.document_id == document_id)
    chunks = query_stmt.all()

    scored = [
        (cosine_similarity(query_vector, chunk.embedding or []), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda item: item[0], reverse=True)

    results = [
        {
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": round(score, 4),
        }
        for score, chunk in scored[:k]
        if score > 0.05
    ]

    record_ai_event(
        db,
        clinic_id=clinic_id,
        event_type="rag_search",
        input_data={"query": query, "k": k},
        output_data={"results": len(results)},
        latency_ms=int((time.monotonic() - start) * 1000),
    )
    return results